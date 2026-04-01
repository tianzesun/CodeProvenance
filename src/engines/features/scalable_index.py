"""
Scalable Code Index using MinHash + LSH (Locality-Sensitive Hashing).

Enables O(n log n) similarity queries over 1B+ code submissions
instead of MOSS's O(n^2) pairwise comparison.

Algorithm:
1. Tokenize code into shingles (k-grams of normalized tokens)
2. Compute MinHash signatures (compact sketch) for each document
3. Index with LSH bands for efficient near-duplicate retrieval
4. Query: hash query → candidate retrieval → exact similarity

Storage:
- MinHash signatures: 200 bytes per submission (vs MBs of raw code)
- LSH index: hash-table buckets, O(n) space
- Query time: O(B * log(n/B)) where B = number of bands
"""
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
import hashlib
import struct
import math
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class MinHashSignature:
    """MinHash signature for a code document."""
    doc_id: str
    hash_values: List[int]
    num_permutations: int = 200

    def jaccard_estimate(self, other: 'MinHashSignature') -> float:
        """Estimate Jaccard similarity between two MinHash signatures."""
        if len(self.hash_values) != len(other.hash_values):
            raise ValueError("Signature lengths must match")
        matches = sum(1 for a, b in zip(self.hash_values, other.hash_values) if a == b)
        return matches / len(self.hash_values)


@dataclass
class LSHEncodedCode:
    """Code document with MinHash + original metadata."""
    doc_id: str
    signature: MinHashSignature
    file_hash: str  # SHA-256 for exact duplicate detection
    token_count: int
    language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenShingler:
    """
    Converts code into shingles (k-grams of normalized tokens).

    Normalization:
    - Identifiers → __ID__
    - String literals → __STR__
    - Numbers → __NUM__
    - Whitespace/comments removed
    """

    def __init__(self, k: int = 5):
        self.k = k

    def shingle(self, code: str, language: str = "python") -> List[str]:
        """
        Tokenize and create k-gram shingles.

        Returns:
            List of shingle strings
        """
        tokens = self._tokenize(code, language)
        if len(tokens) < self.k:
            return [' '.join(tokens)] if tokens else []

        shingles = []
        for i in range(len(tokens) - self.k + 1):
            shingle = ' '.join(tokens[i:i + self.k])
            shingles.append(shingle)
        return shingles

    def _tokenize(self, code: str, language: str) -> List[str]:
        """Tokenize code with normalization."""
        import re

        # Remove comments
        if language == "python":
            code = re.sub(r'#.*?$', '', code, flags=re.MULTILINE)
        else:
            code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)
            code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)

        # Replace string literals
        code = re.sub(r'"[^"]*"', ' __STR__ ', code)
        code = re.sub(r"'[^']*'", ' __STR__ ', code)

        # Replace numbers
        code = re.sub(r'\b\d+(\.\d+)?\b', ' __NUM__ ', code)

        # Normalize identifiers (but keep keywords)
        keywords = self._get_keywords(language)
        tokens = re.findall(r'\b[a-zA-Z_]\w*\b', code)
        normalized = []
        for t in tokens:
            if t in keywords:
                normalized.append(t)
            else:
                normalized.append('__ID__')

        return normalized

    def _get_keywords(self, language: str) -> Set[str]:
        """Get language keywords."""
        if language == "python":
            return {'def', 'class', 'if', 'else', 'elif', 'for', 'while',
                    'return', 'import', 'from', 'try', 'except', 'with',
                    'as', 'lambda', 'yield', 'raise', 'pass', 'break',
                    'continue', 'and', 'or', 'not', 'is', 'in', 'True',
                    'False', 'None', 'print', 'len', 'range', 'self'}
        elif language == "java":
            return {'public', 'private', 'protected', 'static', 'final',
                    'class', 'interface', 'extends', 'implements', 'if',
                    'else', 'for', 'while', 'do', 'switch', 'case',
                    'return', 'void', 'int', 'long', 'float', 'double',
                    'String', 'boolean', 'try', 'catch', 'finally', 'throw',
                    'throws', 'new', 'this', 'super'}
        return set()


class MinHashGenerator:
    """
    Generates MinHash signatures using deterministic hash functions.

    Uses the technique: h_i(x) = (a_i * hash(x) + b_i) mod p
    where a_i, b_i are random coefficients and p is a large prime.
    """

    def __init__(self, num_permutations: int = 200, seed: int = 42):
        self.num_permutations = num_permutations
        self.MAX_HASH = (1 << 32) - 1
        self.MOD_PRIME = (1 << 32) - 5  # Large prime < 2^32

        # Generate deterministic random coefficients
        import random
        rng = random.Random(seed)
        self.coefficients = [
            (rng.randint(1, self.MOD_PRIME - 1),
             rng.randint(0, self.MOD_PRIME - 1))
            for _ in range(num_permutations)
        ]

    def signature(self, shingles: List[str]) -> MinHashSignature:
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
                hash_values=[self.MAX_HASH] * self.num_permutations,
            )

        unique_shingles = set(shingles)
        min_values = [self.MAX_HASH] * self.num_permutations

        for shingle in unique_shingles:
            # Hash this shingle
            h = self._hash_shingle(shingle)

            # Update min for each permutation
            for i, (a, b) in enumerate(self.coefficients):
                perm_hash = (a * h + b) % self.MOD_PRIME
                min_values[i] = min(min_values[i], perm_hash)

        return MinHashSignature(
            doc_id="",
            hash_values=min_values,
            num_permutations=self.num_permutations,
        )

    def _hash_shingle(self, shingle: str) -> int:
        """Hash a single shingle to a 32-bit integer."""
        h = hashlib.md5(shingle.encode('utf-8')).digest()
        return struct.unpack('<I', h[:4])[0]


class LSHIndex:
    """
    Locality-Sensitive Hashing index for near-duplicate retrieval.

    LSH parameters:
    - b: number of bands
    - r: rows per band (b * r = total hash values)

    Similarity threshold: t ≈ (1/b)^(1/r)
    Higher b → lower threshold (more sensitive)
    Higher r → higher threshold (more precise)

    For default b=20, r=10: threshold ≈ 0.63
    """

    def __init__(self, num_bands: int = 20, rows_per_band: int = 10):
        self.num_bands = num_bands
        self.rows_per_band = rows_per_band
        # band_id → hash_bucket → set of doc_ids
        self.buckets: List[Dict[int, Set[str]]] = [
            defaultdict(set) for _ in range(num_bands)
        ]
        # All indexed documents
        self.documents: Dict[str, LSHEncodedCode] = {}
        # Inverted index: shingle → doc_ids (for additional filtering)
        self.shingle_index: Dict[str, Set[str]] = defaultdict(set)

    def add(self, doc: LSHEncodedCode) -> None:
        """
        Add a document to the LSH index.

        Time complexity: O(num_permutations)
        """
        self.documents[doc.doc_id] = doc
        sig = doc.signature.hash_values

        total_hash_values = len(sig)
        assert total_hash_values == self.num_bands * self.rows_per_band

        for band_idx in range(self.num_bands):
            start = band_idx * self.rows_per_band
            end = start + self.rows_per_band
            # Create band hash from the slice
            band_hash = self._hash_band(sig[start:end])
            self.buckets[band_idx][band_hash].add(doc.doc_id)

    def query(self, signature: MinHashSignature,
              min_jaccard: float = 0.5) -> List[Tuple[str, float]]:
        """
        Find near-duplicate documents.

        Time complexity: O(num_bands * log(n))

        Returns:
            List of (doc_id, estimated_jaccard) sorted by similarity desc
        """
        candidates: Set[str] = set()
        sig = signature.hash_values

        for band_idx in range(self.num_bands):
            start = band_idx * self.rows_per_band
            end = start + self.rows_per_band
            band_hash = self._hash_band(sig[start:end])

            # Get all docs that share this band hash
            candidates.update(self.buckets[band_idx].get(band_hash, set()))

        # Compute exact Jaccard estimates for candidates
        results = []
        for cand_id in candidates:
            if cand_id in self.documents:
                other_sig = self.documents[cand_id].signature
                jaccard = signature.jaccard_estimate(other_sig)
                if jaccard >= min_jaccard:
                    results.append((cand_id, jaccard))

        results.sort(key=lambda x: -x[1])
        return results

    def batch_index(self, docs: List[LSHEncodedCode]) -> None:
        """Index a batch of documents."""
        for doc in docs:
            self.add(doc)

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        total_buckets = sum(len(b) for b in self.buckets)
        avg_bucket_size = (
            sum(len(docs) for b in self.buckets for docs in b.values())
            / max(1, total_buckets)
        )

        return {
            "num_documents": len(self.documents),
            "num_bands": self.num_bands,
            "rows_per_band": self.rows_per_band,
            "total_buckets": total_buckets,
            "avg_bucket_size": round(avg_bucket_size, 2),
            "similarity_threshold": round(
                (1 / self.num_bands) ** (1 / self.rows_per_band), 4
            ),
        }

    def _hash_band(self, values: List[int]) -> int:
        """Hash a band of MinHash values."""
        data = struct.pack(f'{len(values)}I', *values)
        return int(hashlib.md5(data).hexdigest()[:8], 16)

    def remove(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        if doc_id not in self.documents:
            return False

        doc = self.documents[doc_id]
        sig = doc.signature.hash_values

        for band_idx in range(self.num_bands):
            start = band_idx * self.rows_per_band
            end = start + self.rows_per_band
            band_hash = self._hash_band(sig[start:end])
            self.buckets[band_idx][band_hash].discard(doc_id)

            # Clean empty buckets
            if not self.buckets[band_idx][band_hash]:
                del self.buckets[band_idx][band_hash]

        del self.documents[doc_id]
        return True


class ScalableCodeIndex:
    """
    High-level interface for scalable code similarity search.

    Combines:
    - TokenShingler for normalization
    - MinHashGenerator for compact signatures
    - LSHIndex for efficient retrieval

    Usage:
        index = ScalableCodeIndex()
        index.add_file("doc1", "def foo(): ...", language="python")
        index.add_file("doc2", "def bar(): ...", language="python")
        results = index.find_similar("def foo(): ...")
    """

    def __init__(self, num_permutations: int = 200,
                 num_bands: int = 20, rows_per_band: int = 10):
        self.shingler = TokenShingler(k=5)
        self.minhash_gen = MinHashGenerator(num_permutations, seed=42)
        self.lsh = LSHIndex(num_bands, rows_per_band)

    def add_file(self, doc_id: str, code: str,
                 language: str = "python",
                 metadata: Dict[str, Any] = None) -> LSHEncodedCode:
        """
        Add a code file to the index.

        Args:
            doc_id: Unique identifier
            code: Source code
            language: Programming language
            metadata: Additional metadata

        Returns:
            LSHEncodedCode
        """
        shingles = self.shingler.shingle(code, language)
        sig = self.minhash_gen.signature(shingles)

        # SHA-256 for exact duplicate detection
        file_hash = hashlib.sha256(code.encode()).hexdigest()

        doc = LSHEncodedCode(
            doc_id=doc_id,
            signature=MinHashSignature(
                doc_id=doc_id,
                hash_values=sig.hash_values,
            ),
            file_hash=file_hash,
            token_count=len(shingles),
            language=language,
            metadata=metadata or {},
        )

        self.lsh.add(doc)
        return doc

    def find_similar(self, code: str, language: str = "python",
                     min_jaccard: float = 0.5,
                     top_k: int = 10) -> List[Tuple[str, float]]:
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
        shingles = self.shingler.shingle(code, language)
        sig = self.minhash_gen.signature(shingles)

        results = self.lsh.query(sig, min_jaccard)
        return results[:top_k]

    def find_exact_duplicates(self, code: str) -> List[str]:
        """Find exact duplicates by file hash."""
        target_hash = hashlib.sha256(code.encode()).hexdigest()
        return [
            doc.doc_id for doc in self.lsh.documents.values()
            if doc.file_hash == target_hash
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return self.lsh.get_stats()