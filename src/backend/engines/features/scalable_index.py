"""
Scalable Code Index using MinHash + LSH (Locality-Sensitive Hashing).

Finds near-duplicate code without comparing every pair: a query touches only the
LSH buckets its signature falls into, instead of MOSS-style O(n^2) comparison.

Algorithm:
1. Tokenize code into shingles (k-grams of normalized tokens)
2. Compute MinHash signatures (compact sketch) for each document
3. Index with LSH bands for efficient near-duplicate retrieval
4. Query: hash query -> candidate retrieval -> Jaccard estimate

Cost model (honest numbers):
- A signature is ``num_permutations`` 32-bit values: 800 bytes packed for the
  default 200. (As a Python list of ints it takes several times that.)
- Index space is O(n * bands); a query does O(bands) bucket lookups plus one
  Jaccard estimate per candidate.
- The index is in memory and per process; it does not persist itself.

Recall caveat: LSH only reliably retrieves documents whose Jaccard similarity is
ABOVE the index threshold ``(1/bands)^(1/rows)``. With the default 20 bands x 10
rows that threshold is about 0.74, so a document at Jaccard 0.5 is retrieved only
about 2% of the time, even though ``find_similar`` defaults to ``min_jaccard=0.5``.
Build the index for the threshold you care about with
``ScalableCodeIndex.for_threshold(0.5)``.
"""

import hashlib
import keyword
import logging
import math
import random
import re
import struct
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from operator import eq
from typing import Any

try:  # vectorised MinHash; the pure-Python path below is the fallback
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a project dependency
    np = None

logger = logging.getLogger(__name__)

_MAX_HASH = (1 << 32) - 1
_MOD_PRIME = (1 << 32) - 5  # largest prime below 2^32
#: Signature value meaning "no shingles". A real value is always < _MOD_PRIME,
#: so it can never equal this.
_EMPTY_HASH = _MAX_HASH
_NUMPY_CHUNK = 2048  # shingles per vectorised block (bounds temporary memory)


@dataclass
class MinHashSignature:
    """MinHash signature for a code document."""

    doc_id: str
    hash_values: list[int]
    num_permutations: int = 200

    def __post_init__(self) -> None:
        # The default of 200 used to be kept even for other signature lengths.
        self.num_permutations = len(self.hash_values)

    @property
    def is_empty(self) -> bool:
        """True for the signature of a document with no shingles."""
        return bool(self.hash_values) and min(self.hash_values) == _EMPTY_HASH

    def jaccard_estimate(self, other: "MinHashSignature") -> float:
        """Estimate Jaccard similarity between two MinHash signatures."""
        if len(self.hash_values) != len(other.hash_values):
            raise ValueError("Signature lengths must match")
        if not self.hash_values:
            return 0.0
        return sum(map(eq, self.hash_values, other.hash_values)) / len(self.hash_values)


@dataclass
class LSHEncodedCode:
    """Code document with MinHash + original metadata."""

    doc_id: str
    signature: MinHashSignature
    file_hash: str  # SHA-256 for exact duplicate detection
    token_count: int
    language: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

_LANGUAGE_ALIASES = {
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "c++": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "h": "c",
    "c#": "csharp",
    "cs": "csharp",
    "rb": "ruby",
    "kt": "kotlin",
    "rs": "rust",
    "sh": "bash",
}

#: Languages whose line comments start with ``#`` (the rest use ``//`` and ``/* */``).
_HASH_COMMENT_LANGUAGES = frozenset({"python", "ruby", "bash", "perl", "r", "powershell", "elixir"})


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


_C_LIKE = (
    "if else for while do switch case default break continue return goto typedef struct "
    "union enum sizeof static const extern volatile void int long short char float double "
    "unsigned signed"
)
_KEYWORDS_BY_LANGUAGE: dict[str, frozenset[str]] = {
    "python": frozenset(keyword.kwlist) | {"print", "len", "range", "self"},
    "java": _words(
        "public private protected static final abstract class interface enum extends "
        "implements import package if else for while do switch case default break continue "
        "return void int long short byte char float double boolean String try catch finally "
        "throw throws new this super null true false instanceof synchronized volatile"
    ),
    "c": _words(_C_LIKE + " NULL include define"),
    "cpp": _words(
        _C_LIKE + " class public private protected virtual template typename namespace using "
        "new delete this try catch throw nullptr true false bool auto operator inline "
        "explicit friend constexpr override"
    ),
    "javascript": _words(
        "var let const function class extends new this super if else for while do switch case "
        "default break continue return try catch finally throw typeof instanceof in of delete "
        "void async await yield import export from null undefined true false"
    ),
    "typescript": _words(
        "var let const function class extends implements interface type enum namespace new this "
        "super if else for while do switch case default break continue return try catch finally "
        "throw typeof instanceof in of delete void async await yield import export from null "
        "undefined true false public private protected readonly abstract static"
    ),
    "go": _words(
        "package import func var const type struct interface map chan go defer select if else "
        "for range switch case default break continue return fallthrough goto nil true false"
    ),
    "rust": _words(
        "fn let mut const static struct enum impl trait pub use mod crate self super match if "
        "else for while loop break continue return as in where move ref async await true false"
    ),
    "csharp": _words(
        "namespace using class struct interface enum public private protected internal static "
        "readonly const virtual override abstract sealed new this base if else for foreach while "
        "do switch case default break continue return try catch finally throw var void int long "
        "string bool null true false async await"
    ),
    "ruby": _words(
        "def end class module if elsif else unless while until for in do begin rescue ensure "
        "return yield self nil true false and or not then case when"
    ),
    "php": _words(
        "function class interface trait extends implements namespace use public private "
        "protected static final abstract new this if else elseif for foreach while do switch "
        "case default break continue return try catch finally throw echo null true false"
    ),
    "kotlin": _words(
        "fun val var class object interface enum data sealed open override abstract import "
        "package if else for while do when break continue return try catch finally throw is in "
        "as null true false this super"
    ),
    "bash": _words(
        "if then else elif fi for while until do done case esac function in select return "
        "break continue exit local export"
    ),
}
#: Used for any language not listed above. An empty set made every identifier AND
#: keyword normalize to ``__ID__``, so any two files in such a language produced
#: identical shingles and looked like exact duplicates of each other.
_GENERIC_KEYWORDS: frozenset[str] = frozenset().union(
    *(_KEYWORDS_BY_LANGUAGE[k] for k in ("python", "java", "javascript", "go", "ruby"))
)

_STR_PREFIX = r"(?:[rRbBuUfF]{1,2})?"
_NUMBER = r"0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
_IDENT = r"[A-Za-z_$][\w$]*"
_TOKEN_PATTERNS: dict[bool, "re.Pattern[str]"] = {}


def _token_pattern(hash_comments: bool) -> "re.Pattern[str]":
    """One scanner for comments, strings, numbers and identifiers.

    Comments and strings are matched in the SAME pass. Removing comments first
    deleted ``# ...`` inside string literals (and everything after ``//`` in a
    URL such as ``"http://x"``), while the string regex ran on text that had
    already lost its comments.
    """
    pattern = _TOKEN_PATTERNS.get(hash_comments)
    if pattern is None:
        comment = r"#[^\n]*" if hash_comments else r"//[^\n]*|/\*.*?\*/"
        triple = (
            r'"""(?:\\.|[^\\])*?"""|\'\'\'(?:\\.|[^\\])*?\'\'\'|' if hash_comments else ""
        )
        string = (
            rf"{_STR_PREFIX}(?:{triple}\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'"
            + ("" if hash_comments else r"|`(?:\\.|[^`\\])*`")
            + ")"
        )
        pattern = re.compile(
            rf"(?P<comment>{comment})|(?P<string>{string})|(?P<number>{_NUMBER})|(?P<ident>{_IDENT})",
            re.DOTALL,
        )
        _TOKEN_PATTERNS[hash_comments] = pattern
    return pattern


def normalize_language(language: str | None) -> str:
    """Lower-case a language name and resolve common aliases (``js`` -> ``javascript``)."""
    name = (language or "python").strip().lower()
    return _LANGUAGE_ALIASES.get(name, name)


class TokenShingler:
    """
    Converts code into shingles (k-grams of normalized tokens).

    Normalization:
    - Identifiers -> __ID__ (language keywords are kept)
    - String literals -> __STR__
    - Numbers -> __NUM__
    - Whitespace/comments removed
    """

    def __init__(self, k: int = 5):
        if k < 1:
            raise ValueError("k must be at least 1")
        self.k = k

    def shingle(self, code: str, language: str = "python") -> list[str]:
        """
        Tokenize and create k-gram shingles.

        Returns:
            List of shingle strings
        """
        return self.shingles_from_tokens(self.tokenize(code, language))

    def shingles_from_tokens(self, tokens: list[str]) -> list[str]:
        """k-grams of an already tokenized document."""
        k = self.k
        if len(tokens) < k:
            return [" ".join(tokens)] if tokens else []
        return [" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)]

    def tokenize(self, code: str, language: str = "python") -> list[str]:
        """Tokenize code with normalization."""
        language = normalize_language(language)
        keywords = self._get_keywords(language)
        scanner = _token_pattern(language in _HASH_COMMENT_LANGUAGES)

        tokens: list[str] = []
        append = tokens.append
        for match in scanner.finditer(code):
            kind = match.lastgroup
            if kind == "comment":
                continue
            if kind == "string":
                append("__STR__")
            elif kind == "number":
                # The placeholder used to be re-tokenized as an identifier, so
                # numbers and strings both ended up as ``__ID__``.
                append("__NUM__")
            else:
                word = match.group()
                append(word if word in keywords else "__ID__")
        return tokens

    def _tokenize(self, code: str, language: str) -> list[str]:
        return self.tokenize(code, language)

    def _get_keywords(self, language: str) -> set[str] | frozenset[str]:
        """Get language keywords (a generic set for unknown languages)."""
        return _KEYWORDS_BY_LANGUAGE.get(normalize_language(language), _GENERIC_KEYWORDS)


# ---------------------------------------------------------------------------
# MinHash
# ---------------------------------------------------------------------------


class MinHashGenerator:
    """
    Generates MinHash signatures using deterministic hash functions.

    Uses the technique: h_i(x) = (a_i * hash(x) + b_i) mod p
    where a_i, b_i are random coefficients and p is a large prime.

    With numpy the permutations are applied to blocks of shingles at once (the
    pure-Python double loop did ``shingles x permutations`` interpreter steps).
    Both paths produce identical signatures.
    """

    def __init__(self, num_permutations: int = 200, seed: int = 42):
        if num_permutations < 1:
            raise ValueError("num_permutations must be at least 1")
        self.num_permutations = num_permutations
        self.MAX_HASH = _MAX_HASH
        self.MOD_PRIME = _MOD_PRIME

        # Generate deterministic random coefficients
        rng = random.Random(seed)
        self.coefficients = [
            (rng.randint(1, self.MOD_PRIME - 1), rng.randint(0, self.MOD_PRIME - 1))
            for _ in range(num_permutations)
        ]
        if np is not None:
            # a, h < 2^32 so a*h + b < 2^64: exact in uint64, no overflow.
            self._a = np.array([a for a, _ in self.coefficients], dtype=np.uint64)[:, None]
            self._b = np.array([b for _, b in self.coefficients], dtype=np.uint64)[:, None]
            self._mod = np.uint64(self.MOD_PRIME)

    def signature(self, shingles: list[str]) -> MinHashSignature:
        """
        Compute MinHash signature for a set of shingles.

        Args:
            shingles: List of shingles (duplicates removed internally)

        Returns:
            MinHashSignature
        """
        if not shingles:
            return MinHashSignature(
                doc_id="",
                hash_values=[_EMPTY_HASH] * self.num_permutations,
            )

        hashes = [self._hash_shingle(s) for s in set(shingles)]
        values = (
            self._signature_numpy(hashes) if np is not None else self._signature_python(hashes)
        )
        return MinHashSignature(
            doc_id="",
            hash_values=values,
            num_permutations=self.num_permutations,
        )

    def _signature_python(self, hashes: list[int]) -> list[int]:
        min_values = [self.MAX_HASH] * self.num_permutations
        mod = self.MOD_PRIME
        for h in hashes:
            for i, (a, b) in enumerate(self.coefficients):
                value = (a * h + b) % mod
                if value < min_values[i]:
                    min_values[i] = value
        return min_values

    def _signature_numpy(self, hashes: list[int]) -> list[int]:
        values = np.fromiter(hashes, dtype=np.uint64, count=len(hashes))
        mins = np.full(self.num_permutations, self.MAX_HASH, dtype=np.uint64)
        for start in range(0, len(values), _NUMPY_CHUNK):
            block = values[start : start + _NUMPY_CHUNK][None, :]
            permuted = (self._a * block + self._b) % self._mod
            np.minimum(mins, permuted.min(axis=1), out=mins)
        return mins.tolist()

    def _hash_shingle(self, shingle: str) -> int:
        """Hash a single shingle to a 32-bit integer (BLAKE2b; MD5 is not used)."""
        digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=4).digest()
        return int.from_bytes(digest, "little")


# ---------------------------------------------------------------------------
# LSH
# ---------------------------------------------------------------------------


def candidate_probability(similarity: float, num_bands: int, rows_per_band: int) -> float:
    """P(two documents with this Jaccard similarity share at least one band)."""
    return 1.0 - (1.0 - similarity**rows_per_band) ** num_bands


def optimal_lsh_params(
    num_permutations: int,
    threshold: float,
    false_positive_weight: float = 0.5,
    false_negative_weight: float = 0.5,
) -> tuple[int, int]:
    """Choose ``(bands, rows)`` with ``bands * rows == num_permutations``.

    Minimises the weighted area of false positives (candidate probability below
    ``threshold``) and false negatives (missed probability above it).
    """
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be between 0 and 1")
    steps = 400
    best: tuple[float, tuple[int, int]] | None = None
    for bands in range(1, num_permutations + 1):
        if num_permutations % bands:
            continue
        rows = num_permutations // bands
        false_pos = false_neg = 0.0
        for i in range(steps):
            s = (i + 0.5) / steps
            p = candidate_probability(s, bands, rows)
            if s < threshold:
                false_pos += p / steps
            else:
                false_neg += (1.0 - p) / steps
        cost = false_positive_weight * false_pos + false_negative_weight * false_neg
        if best is None or cost < best[0]:
            best = (cost, (bands, rows))
    assert best is not None
    return best[1]


class LSHIndex:
    """
    Locality-Sensitive Hashing index for near-duplicate retrieval.

    LSH parameters:
    - b: number of bands
    - r: rows per band (b * r = total hash values)

    Similarity threshold: t ~= (1/b)^(1/r)
    Higher b -> lower threshold (more sensitive)
    Higher r -> higher threshold (more precise)

    For default b=20, r=10 the threshold is about 0.74 (the docstring used to
    say 0.63). Documents well below it are rarely retrieved; see
    :func:`candidate_probability`.

    Thread-safe: adds, removals and queries are serialised by one lock.
    """

    def __init__(self, num_bands: int = 20, rows_per_band: int = 10):
        if num_bands < 1 or rows_per_band < 1:
            raise ValueError("num_bands and rows_per_band must be at least 1")
        self.num_bands = num_bands
        self.rows_per_band = rows_per_band
        # band_id -> hash_bucket -> set of doc_ids
        self.buckets: list[dict[int, set[str]]] = [defaultdict(set) for _ in range(num_bands)]
        # All indexed documents
        self.documents: dict[str, LSHEncodedCode] = {}
        self._band_struct = struct.Struct(f"{rows_per_band}I")
        self._lock = threading.RLock()

    @property
    def expected_signature_length(self) -> int:
        return self.num_bands * self.rows_per_band

    @property
    def similarity_threshold(self) -> float:
        return (1 / self.num_bands) ** (1 / self.rows_per_band)

    def candidate_probability(self, similarity: float) -> float:
        """P(a document at this Jaccard similarity is retrieved as a candidate)."""
        return candidate_probability(similarity, self.num_bands, self.rows_per_band)

    def _check_length(self, signature: MinHashSignature) -> None:
        if len(signature.hash_values) != self.expected_signature_length:
            # Was an ``assert`` (removed under ``python -O``) raised only at add time.
            raise ValueError(
                f"Signature has {len(signature.hash_values)} values; this index needs "
                f"{self.expected_signature_length} ({self.num_bands} bands x {self.rows_per_band} rows)"
            )

    def _band_hashes(self, values: list[int]) -> list[int]:
        rows = self.rows_per_band
        return [
            self._hash_band(values[b * rows : (b + 1) * rows]) for b in range(self.num_bands)
        ]

    def add(self, doc: LSHEncodedCode) -> None:
        """
        Add a document to the LSH index.

        Re-adding an existing ``doc_id`` replaces it. The old signature's bucket
        entries used to be left behind. A document with no shingles is stored but
        not bucketed: every empty document has the same signature, so bucketing
        them made all of them near-duplicates of each other.

        Time complexity: O(num_permutations)
        """
        self._check_length(doc.signature)
        with self._lock:
            if doc.doc_id in self.documents:
                self._remove_locked(doc.doc_id)
            self.documents[doc.doc_id] = doc
            if doc.signature.is_empty:
                return
            for band_idx, band_hash in enumerate(self._band_hashes(doc.signature.hash_values)):
                self.buckets[band_idx][band_hash].add(doc.doc_id)

    def query(
        self, signature: MinHashSignature, min_jaccard: float = 0.5
    ) -> list[tuple[str, float]]:
        """
        Find near-duplicate documents.

        Time complexity: O(num_bands) bucket lookups + one estimate per candidate.

        Returns:
            List of (doc_id, estimated_jaccard) sorted by similarity desc
        """
        self._check_length(signature)
        if signature.is_empty:
            return []

        with self._lock:
            candidates: set[str] = set()
            for band_idx, band_hash in enumerate(self._band_hashes(signature.hash_values)):
                bucket = self.buckets[band_idx].get(band_hash)
                if bucket:
                    candidates.update(bucket)

            results = []
            for cand_id in candidates:
                doc = self.documents.get(cand_id)
                if doc is None:
                    continue
                jaccard = signature.jaccard_estimate(doc.signature)
                if jaccard >= min_jaccard:
                    results.append((cand_id, jaccard))

        results.sort(key=lambda x: (-x[1], x[0]))
        return results

    def batch_index(self, docs: list[LSHEncodedCode]) -> None:
        """Index a batch of documents."""
        for doc in docs:
            self.add(doc)

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        with self._lock:
            total_buckets = sum(len(b) for b in self.buckets)
            total_entries = sum(len(docs) for b in self.buckets for docs in b.values())
            return {
                "num_documents": len(self.documents),
                "num_bands": self.num_bands,
                "rows_per_band": self.rows_per_band,
                "total_buckets": total_buckets,
                "avg_bucket_size": round(total_entries / max(1, total_buckets), 2),
                "similarity_threshold": round(self.similarity_threshold, 4),
            }

    def _hash_band(self, values: list[int]) -> int:
        """Hash a band of MinHash values to a 64-bit bucket key (BLAKE2b)."""
        data = self._band_struct.pack(*values)
        return int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), "little")

    def remove(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        with self._lock:
            return self._remove_locked(doc_id)

    def _remove_locked(self, doc_id: str) -> bool:
        doc = self.documents.get(doc_id)
        if doc is None:
            return False

        if not doc.signature.is_empty:
            for band_idx, band_hash in enumerate(self._band_hashes(doc.signature.hash_values)):
                bucket = self.buckets[band_idx].get(band_hash)
                if bucket is None:
                    continue
                bucket.discard(doc_id)
                if not bucket:  # clean empty buckets
                    del self.buckets[band_idx][band_hash]

        del self.documents[doc_id]
        return True


# ---------------------------------------------------------------------------
# High-level index
# ---------------------------------------------------------------------------


class ScalableCodeIndex:
    """
    High-level interface for scalable code similarity search.

    Combines:
    - TokenShingler for normalization
    - MinHashGenerator for compact signatures
    - LSHIndex for efficient retrieval

    Usage:
        index = ScalableCodeIndex.for_threshold(0.5)
        index.add_file("doc1", "def foo(): ...", language="python")
        index.add_file("doc2", "def bar(): ...", language="python")
        results = index.find_similar("def foo(): ...")
    """

    def __init__(
        self,
        num_permutations: int = 200,
        num_bands: int = 20,
        rows_per_band: int = 10,
        shingle_size: int = 5,
    ):
        if num_bands * rows_per_band != num_permutations:
            # Previously this surfaced later, as an AssertionError on the first add.
            raise ValueError(
                f"num_bands * rows_per_band ({num_bands * rows_per_band}) must equal "
                f"num_permutations ({num_permutations})"
            )
        self.shingler = TokenShingler(k=shingle_size)
        self.minhash_gen = MinHashGenerator(num_permutations, seed=42)
        self.lsh = LSHIndex(num_bands, rows_per_band)
        self._hash_index: dict[str, set[str]] = defaultdict(set)  # file hash -> doc ids
        self._lock = threading.RLock()
        self._warned_low_recall = False

    @classmethod
    def for_threshold(
        cls, threshold: float, num_permutations: int = 200, shingle_size: int = 5
    ) -> "ScalableCodeIndex":
        """Build an index whose LSH bands are tuned for retrieving ``threshold``."""
        bands, rows = optimal_lsh_params(num_permutations, threshold)
        return cls(num_permutations, bands, rows, shingle_size)

    def __len__(self) -> int:
        return len(self.lsh.documents)

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self.lsh.documents

    def add_file(
        self,
        doc_id: str,
        code: str,
        language: str = "python",
        metadata: dict[str, Any] | None = None,
    ) -> LSHEncodedCode:
        """
        Add a code file to the index (replacing any file with the same id).

        Args:
            doc_id: Unique identifier
            code: Source code
            language: Programming language
            metadata: Additional metadata

        Returns:
            LSHEncodedCode
        """
        language = normalize_language(language)
        tokens = self.shingler.tokenize(code, language)
        sig = self.minhash_gen.signature(self.shingler.shingles_from_tokens(tokens))

        # SHA-256 for exact duplicate detection
        file_hash = hashlib.sha256(code.encode("utf-8", "surrogatepass")).hexdigest()

        doc = LSHEncodedCode(
            doc_id=doc_id,
            signature=MinHashSignature(doc_id=doc_id, hash_values=sig.hash_values),
            file_hash=file_hash,
            # Number of tokens (it used to be the shingle count, i.e. tokens - k + 1).
            token_count=len(tokens),
            language=language,
            metadata=metadata or {},
        )

        with self._lock:
            if doc_id in self.lsh.documents:
                self.remove_file(doc_id)
            self.lsh.add(doc)
            self._hash_index[file_hash].add(doc_id)
        return doc

    def remove_file(self, doc_id: str) -> bool:
        """Remove a file from the index; False if it was not indexed."""
        with self._lock:
            doc = self.lsh.documents.get(doc_id)
            if doc is None:
                return False
            self.lsh.remove(doc_id)
            ids = self._hash_index.get(doc.file_hash)
            if ids is not None:
                ids.discard(doc_id)
                if not ids:
                    del self._hash_index[doc.file_hash]
            return True

    def find_similar(
        self,
        code: str,
        language: str = "python",
        min_jaccard: float = 0.5,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """
        Find similar code in the index.

        Args:
            code: Query code
            language: Programming language
            min_jaccard: Minimum Jaccard similarity
            top_k: Maximum results to return

        Returns:
            List of (doc_id, similarity) sorted by similarity desc
        """
        if not self._warned_low_recall and self.lsh.candidate_probability(min_jaccard) < 0.5:
            self._warned_low_recall = True
            logger.warning(
                "min_jaccard=%.2f is below this index's LSH threshold (%.2f): a document at "
                "that similarity is retrieved only %.0f%% of the time. Build the index with "
                "ScalableCodeIndex.for_threshold(%.2f) for reliable recall.",
                min_jaccard,
                self.lsh.similarity_threshold,
                100 * self.lsh.candidate_probability(min_jaccard),
                min_jaccard,
            )
        shingles = self.shingler.shingle(code, language)
        sig = self.minhash_gen.signature(shingles)

        results = self.lsh.query(sig, min_jaccard)
        return results[:top_k]

    def find_exact_duplicates(self, code: str) -> list[str]:
        """Find exact duplicates by file hash (a dictionary lookup, not a scan)."""
        target_hash = hashlib.sha256(code.encode("utf-8", "surrogatepass")).hexdigest()
        with self._lock:
            return sorted(self._hash_index.get(target_hash, ()))

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        stats = self.lsh.get_stats()
        stats["distinct_file_hashes"] = len(self._hash_index)
        return stats
