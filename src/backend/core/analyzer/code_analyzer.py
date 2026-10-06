"""Lightweight compatibility analyzer used by legacy integration tests."""

from __future__ import annotations

import importlib
import keyword
import logging
import math
import re
import sys
import zlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)

PYTHON_KEYWORDS = set(keyword.kwlist)
GENERIC_KEYWORDS = {
    "class", "const", "def", "else", "false", "for", "function", "if", "import",
    "in", "let", "none", "null", "return", "static", "true", "var", "while",
}  # fmt: skip
JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class",
    "const", "continue", "default", "do", "double", "else", "enum", "extends", "false",
    "final", "finally", "float", "for", "if", "implements", "import", "instanceof",
    "int", "interface", "long", "new", "null", "package", "private", "protected",
    "public", "return", "short", "static", "super", "switch", "synchronized", "this",
    "throw", "throws", "true", "try", "var", "void", "volatile", "while",
}  # fmt: skip
JAVASCRIPT_KEYWORDS = {
    "async", "await", "break", "case", "catch", "class", "const", "continue",
    "debugger", "default", "delete", "do", "else", "export", "extends", "false",
    "finally", "for", "function", "if", "import", "in", "instanceof", "let", "new",
    "null", "return", "static", "super", "switch", "this", "throw", "true", "try",
    "typeof", "var", "void", "while", "yield",
}  # fmt: skip

# Exact, per-language keyword sets. The old shared set treated Python identifiers
# such as `var`/`function`/`static` as keywords (defeating rename-resistance) and
# treated Java/JS keywords such as `public`/`new`/`try` as plain identifiers.
_LANGUAGE_KEYWORDS: dict[str, set[str]] = {
    "python": PYTHON_KEYWORDS,
    "java": JAVA_KEYWORDS,
    "javascript": JAVASCRIPT_KEYWORDS,
}
_LITERAL_ALIASES = {"none": "null"}
_LANGUAGE_ALIASES = {
    "py": "python", "python3": "python",
    "js": "javascript", "jsx": "javascript", "ts": "javascript",
    "tsx": "javascript", "typescript": "javascript", "node": "javascript",
}  # fmt: skip


@dataclass
class CodeAnalysisResult:
    """Summary of a single source file analysis."""

    file_path: str
    language: str
    line_count: int
    token_count: int
    code_hash: str
    ai_detection: dict[str, float | bool]
    complexity_metrics: dict[str, int | float]


@dataclass
class CodeComparisonResult:
    """Pairwise similarity result."""

    file_a: str
    file_b: str
    overall_score: float
    individual_scores: dict[str, float]
    is_suspicious: bool
    language_a: str
    language_b: str


# (weight, key) - weights sum to 1.0 when every signal is available.
_SIGNAL_WEIGHTS = {
    "token": 0.08, "ngram": 0.10, "winnowing": 0.07, "structure": 0.10,
    "sequence": 0.08, "graph": 0.14, "merge": 0.10, "ast": 0.28, "tfidf": 0.05,
}  # fmt: skip


class CodeAnalyzer:
    """Simple multi-signal analyzer compatible with the historic API."""

    def __init__(self, threshold: float = 0.5, enable_ai_detection: bool = True):
        self.threshold = threshold
        self.enable_ai_detection = enable_ai_detection

    def analyze_code(
        self,
        code: str,
        language: str,
        file_path: str | None = None,
    ) -> CodeAnalysisResult:
        tokens = _lexical_tokens(code, language)
        line_count = (
            len([line for line in code.splitlines() if line.strip()])
            or len(code.splitlines())
            or 1
        )
        token_count = len(tokens)

        # Count on real tokens, not raw text: words inside comments/strings and
        # identifiers like `match` or `obj.function` no longer inflate metrics.
        function_count = branch_count = 0
        previous = ""
        for token in tokens:
            if previous != ".":
                if token in {"def", "function"}:
                    function_count += 1
                elif token in _BRANCH_TOKENS:
                    branch_count += 1
            if token == "=>":
                function_count += 1
            previous = token

        return CodeAnalysisResult(
            file_path=file_path or "<memory>",
            language=language,
            line_count=line_count,
            token_count=token_count,
            code_hash=sha256(code.encode("utf-8")).hexdigest(),
            ai_detection=self._detect_ai(code, language),
            complexity_metrics={
                "line_count": line_count,
                "token_count": token_count,
                "function_count": function_count,
                "branch_count": branch_count,
            },
        )

    def compare_codes(
        self,
        code_a: str,
        code_b: str,
        language_a: str,
        language_b: str,
        file_a: str | None = None,
        file_b: str | None = None,
    ) -> CodeComparisonResult:
        normalized_a = _normalized_tokens(code_a, language_a)
        normalized_b = _normalized_tokens(code_b, language_b)

        ast = _ast_cfg_pdg_similarity(code_a, code_b, language_a, language_b)
        ast_available = bool(ast.get("available", 1.0))

        signals = {
            "token": _jaccard(normalized_a, normalized_b),
            "ngram": _ngram_similarity(normalized_a, normalized_b, size=3),
            "winnowing": _winnowing_similarity(normalized_a, normalized_b),
            "structure": _structure_similarity(code_a, code_b, language_a, language_b),
            "sequence": _sequence_similarity(normalized_a, normalized_b),
            "graph": _normalization_graph_similarity(normalized_a, normalized_b),
            "merge": _merged_subsequence_similarity(normalized_a, normalized_b),
            "ast": float(ast["similarity"]),
            "tfidf": _tfidf_similarity(code_a, code_b, language_a),
        }
        signals = {key: _clamp01(value) for key, value in signals.items()}

        # Renormalise over the signals that actually ran. Before, a non-Python
        # pair (or a missing AST engine) silently lost 28% of the weight, so
        # byte-identical Java/JS files could never score above 0.72.
        active = {
            k: w for k, w in _SIGNAL_WEIGHTS.items() if k != "ast" or ast_available
        }
        overall_score = _clamp01(
            sum(active[k] * signals[k] for k in active) / sum(active.values())
        )

        scores = {
            "token_similarity": signals["token"],
            "ngram_similarity": signals["ngram"],
            "winnowing_similarity": signals["winnowing"],
            "structure_similarity": signals["structure"],
            "sequence_similarity": signals["sequence"],
            "normalization_graph_similarity": signals["graph"],
            "subsequence_merge_similarity": signals["merge"],
            "ast_cfg_pdg_similarity": signals["ast"],
            "normalized_ast_similarity": _clamp01(ast["ast_sim"]),
            "cfg_similarity": _clamp01(ast["cfg_sim"]),
            "pdg_similarity": _clamp01(ast["pdg_sim"]),
            "tfidf_similarity": signals["tfidf"],
        }

        return CodeComparisonResult(
            file_a=file_a or "code_a",
            file_b=file_b or "code_b",
            overall_score=overall_score,
            individual_scores=scores,
            is_suspicious=overall_score >= self.threshold,
            language_a=language_a,
            language_b=language_b,
        )

    def analyze_pairwise(
        self, submissions: dict[str, str]
    ) -> list[CodeComparisonResult]:
        results: list[CodeComparisonResult] = []
        languages = {
            name: detect_language(name, code) for name, code in submissions.items()
        }
        for file_a, file_b in combinations(sorted(submissions), 2):
            results.append(
                self.compare_codes(
                    submissions[file_a],
                    submissions[file_b],
                    languages[file_a],
                    languages[file_b],
                    file_a,
                    file_b,
                )
            )
        return results

    def find_suspicious_pairs(
        self,
        submissions: dict[str, str],
        threshold: float | None = None,
    ) -> list[CodeComparisonResult]:
        effective_threshold = self.threshold if threshold is None else threshold
        results = [
            result
            for result in self.analyze_pairwise(submissions)
            if result.overall_score >= effective_threshold
        ]
        return sorted(results, key=lambda result: result.overall_score, reverse=True)

    def _detect_ai(
        self, code: str, language: str = "python"
    ) -> dict[str, float | bool]:
        # Same keys whether or not detection is enabled (consumers index into this).
        if not self.enable_ai_detection:
            return {
                "is_likely_ai": False,
                "ai_score": 0.0,
                "heuristic_ai_score": 0.0,
                "model_ai_score": 0.0,
                "model_confidence": 0.0,
            }

        comments = _comment_texts(code, language)
        code_lines = max(1, len([line for line in code.splitlines() if line.strip()]))
        explanatory = sum(1 for c in comments if _EXPLANATORY_RE.search(c.lower()))
        # Density, not absolute counts. The old heuristic added 0.05 per indented
        # line (so any 8+ line function body looked "AI"), and its `^\s{4,}` regex
        # also matched across blank lines.
        heuristic_score = _clamp01(
            2.0 * explanatory / code_lines + 0.5 * len(comments) / code_lines
        )

        model_result = _model_ai_detection(code)
        model_score = _clamp01(model_result.get("ai_probability", 0.0))
        model_confidence = _clamp01(model_result.get("confidence", 0.0))
        if model_result.get("available", True) and (
            model_confidence > 0 or model_score > 0
        ):
            score = 0.65 * model_score + 0.35 * heuristic_score
        else:  # old max(...) meant the model could only ever raise the score
            score = heuristic_score
        return {
            "is_likely_ai": score >= 0.4,
            "ai_score": round(score, 3),
            "heuristic_ai_score": round(heuristic_score, 3),
            "model_ai_score": round(model_score, 3),
            "model_confidence": round(model_confidence, 3),
        }


def analyze_single_code(
    code: str,
    language: str,
    file_path: str | None = None,
) -> CodeAnalysisResult:
    """Analyze a single snippet using default settings."""
    return CodeAnalyzer().analyze_code(code, language, file_path=file_path)


def compare_two_codes(
    code_a: str,
    code_b: str,
    language: str,
    *,
    file_a: str | None = None,
    file_b: str | None = None,
) -> CodeComparisonResult:
    """Compare two snippets using the same language for both sides."""
    return CodeAnalyzer().compare_codes(
        code_a, code_b, language, language, file_a=file_a, file_b=file_b
    )


# --- language detection -------------------------------------------------------------

_BRANCH_TOKENS = frozenset(
    {"if", "elif", "else", "for", "while", "case", "switch", "catch", "except"}
)
_EXPLANATORY_RE = re.compile(r"\b(this|here|check|handle|calculate|return|function)\b")


def detect_language(name: str, code: str = "") -> str:
    """Detect language from extension, falling back to content sniffing.

    Public so batch code uses the *same* detection as pairwise comparison
    (they previously disagreed for extension-less / unknown names).
    """
    suffix = Path(name).suffix.lower()
    if suffix in {".py", ".pyw"}:
        return "python"
    if suffix == ".java":
        return "java"
    if suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return "javascript"
    if re.search(r"^\s*def\s+\w+.*:", code, flags=re.MULTILINE):
        return "python"
    if re.search(r"\b(public|private|protected)\b[^\n]*\{|System\.out\.", code):
        return "java"
    if re.search(r"\bfunction\b|=>", code):
        return "javascript"
    return "python"


_detect_language = detect_language  # backwards-compatible private alias


def _normalize_language(language: str) -> str:
    lang = (language or "").strip().lower()
    return _LANGUAGE_ALIASES.get(lang, lang)


# --- lexing ---------------------------------------------------------------------------
# One left-to-right scanner recognises comments, strings, numbers, identifiers and
# operators together. The old regex-based comment stripping ran first and was
# unaware of strings and languages: in Python `a // b` (floor division) deleted
# the rest of the line, and "http://x" or "#" inside strings were truncated.

_PFX = r"(?:[rRbBuUfF]{1,2})?"
_PY_STRING = "|".join(
    [
        _PFX + r'"""[\s\S]*?"""',
        _PFX + r"'''[\s\S]*?'''",
        _PFX + r'"(?:\\.|[^"\\\n])*"',
        _PFX + r"'(?:\\.|[^'\\\n])*'",
    ]
)
_C_STRING = (
    r'"""[\s\S]*?"""|'
    r'"(?:\\.|[^"\\\n])*"|'
    r"'(?:\\.|[^'\\\n])*'|"
    r"`(?:\\.|[^`\\])*`"
)
_NUMBER = r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+"
_IDENT = r"(?:[^\W\d]|\$)[\w$]*"
_OPERATOR = r"\*\*=?|//=?|<<=?|>>=?|\.\.\.|->|=>|:=|\+\+|--|&&|\|\||[-+*/%&|^<>=!]=|\S"


def _build_scanner(string_pattern: str, comment_pattern: str) -> re.Pattern[str]:
    return re.compile(
        f"(?P<comment>{comment_pattern})|(?P<string>{string_pattern})"
        f"|(?P<number>{_NUMBER})|(?P<ident>{_IDENT})|(?P<op>{_OPERATOR})"
    )


_SCANNERS = {
    "python": _build_scanner(_PY_STRING, r"#[^\n]*"),
    "c": _build_scanner(_C_STRING, r"//[^\n]*|/\*[\s\S]*?\*/"),
}


@lru_cache(maxsize=512)
def _scan(code: str, family: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (m.lastgroup or "op", m.group()) for m in _SCANNERS[family].finditer(code)
    )


def _family(language: str) -> str:
    return "python" if _normalize_language(language) == "python" else "c"


def _lexical_tokens(code: str, language: str = "python") -> list[str]:
    return [text for kind, text in _scan(code, _family(language)) if kind != "comment"]


def _comment_texts(code: str, language: str = "python") -> list[str]:
    return [text for kind, text in _scan(code, _family(language)) if kind == "comment"]


def _normalized_tokens(code: str, language: str) -> list[str]:
    return list(_normalized_tokens_cached(code, _normalize_language(language)))


@lru_cache(maxsize=512)
def _normalized_tokens_cached(code: str, language: str) -> tuple[str, ...]:
    keywords = _LANGUAGE_KEYWORDS.get(language, GENERIC_KEYWORDS)
    out: list[str] = []
    for kind, text in _scan(code, _family(language)):
        if kind == "comment":
            continue
        if kind == "ident":
            if text in keywords:  # exact match: an identifier `If` is not `if`
                lowered = text.lower()
                out.append(_LITERAL_ALIASES.get(lowered, lowered))
            else:
                out.append("ID")
        elif kind == "number":
            out.append("NUM")
        elif kind == "string":
            out.append("STR")  # whole literal; previously each quote char was STR
        else:
            out.append(text)
    return tuple(out)


# --- similarity signals ---------------------------------------------------------------


def _clamp01(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number):
        return 0.0
    return max(0.0, min(1.0, number))


def _normalization_graph_similarity(
    tokens_a: Sequence[str], tokens_b: Sequence[str]
) -> float:
    """Compare normalized token transition graphs for obfuscation-resistant similarity."""
    nodes_a, edges_a = _token_normalization_graph(tokens_a)
    nodes_b, edges_b = _token_normalization_graph(tokens_b)
    if not nodes_a and not nodes_b:
        return 1.0
    return 0.35 * _set_similarity(nodes_a, nodes_b) + 0.65 * _set_similarity(
        edges_a, edges_b
    )


def _token_normalization_graph(
    tokens: Sequence[str],
) -> tuple[set[str], set[tuple[str, str]]]:
    canonical = [_canonical_graph_token(token) for token in tokens]
    nodes = set(canonical)
    edges = {(canonical[i], canonical[i + 1]) for i in range(len(canonical) - 1)}
    return nodes, edges


_OP_RE = re.compile(r"[-+*/%&|^<>=!]=?|\*\*=?|//=?|<<=?|>>=?|&&|\|\||\+\+|--|->|=>|:=")


def _canonical_graph_token(token: str) -> str:
    if token in {"ID", "NUM", "STR"}:
        return token
    if token in {"def", "function", "class", "return", "if", "else", "for", "while"}:
        return f"KW:{token}"
    if _OP_RE.fullmatch(token):
        return "OP"
    if token in {"(", ")", "[", "]", "{", "}", ":", ";", ","}:
        return f"PUNC:{token}"
    return token


def _merged_subsequence_similarity(
    tokens_a: Sequence[str], tokens_b: Sequence[str]
) -> float:
    """Score copied subsequences after merging matches split by small edits."""
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    blocks = [
        b
        for b in SequenceMatcher(
            a=tokens_a, b=tokens_b, autojunk=False
        ).get_matching_blocks()
        if b.size > 0
    ]
    if not blocks:
        return 0.0

    # [a_start, b_start, a_end, b_end]. Each side keeps its own span: the old code
    # measured the merged span on side A only and reused it as side B's coverage.
    merged: list[list[int]] = []
    for block in blocks:
        a_end, b_end = block.a + block.size, block.b + block.size
        if merged:
            last = merged[-1]
            if 0 <= block.a - last[2] <= 3 and 0 <= block.b - last[3] <= 3:
                last[2], last[3] = a_end, b_end
                continue
        merged.append([block.a, block.b, a_end, b_end])

    coverage_a = sum(m[2] - m[0] for m in merged) / len(tokens_a)
    coverage_b = sum(m[3] - m[1] for m in merged) / len(tokens_b)
    if coverage_a + coverage_b == 0:
        return 0.0
    return 2 * coverage_a * coverage_b / (coverage_a + coverage_b)


def _set_similarity(items_a: set, items_b: set) -> float:  # type: ignore[type-arg]
    """Jaccard similarity; two empty sets are identical."""
    if not items_a and not items_b:
        return 1.0
    return len(items_a & items_b) / len(items_a | items_b)


# --- optional engines -------------------------------------------------------------------

_FAILED_IMPORTS: set[str] = set()
_WARNED: set[str] = set()


def _import_optional(name: str) -> ModuleType | None:
    """Import an optional engine; remember failures so we don't retry per pair."""
    module = sys.modules.get(name)
    if module is not None:
        return module
    if name in _FAILED_IMPORTS:
        return None
    try:
        return importlib.import_module(name)
    except ImportError:
        logger.debug("Optional module %s unavailable", name)
    except Exception:
        logger.warning("Optional module %s failed to import", name, exc_info=True)
    _FAILED_IMPORTS.add(name)
    return None


def _warn_once(key: str, message: str) -> None:
    if key not in _WARNED:
        _WARNED.add(key)
        logger.warning(message)


def _model_ai_detection(code: str) -> dict[str, float | bool]:
    """Run the model-backed AI detector when its dependencies are available."""
    unavailable: dict[str, float | bool] = {
        "ai_probability": 0.0, "confidence": 0.0, "available": False,
    }  # fmt: skip
    module = _import_optional("src.backend.engines.similarity.ai_detection")
    engine_cls = getattr(module, "AIDetectionEngine", None)
    if engine_cls is None:
        return unavailable
    try:
        result = engine_cls().analyze(code)
        return {
            "ai_probability": _clamp01(result.get("ai_probability", 0.0)),
            "confidence": _clamp01(result.get("confidence", 0.0)),
            "available": True,
        }
    except Exception:
        _warn_once("ai_detection", "AI detection engine failed; using heuristics only")
        return unavailable


def _ast_cfg_pdg_similarity(
    code_a: str, code_b: str, language: str, language_b: str | None = None
) -> dict[str, float]:
    """Compare normalized AST, CFG and PDG structure (Python/Python only).

    ``available`` is 0.0 when the signal could not run, so the caller can drop it
    instead of counting it as "0% similar".
    """
    none: dict[str, float] = {
        "similarity": 0.0, "ast_sim": 0.0, "cfg_sim": 0.0, "pdg_sim": 0.0, "available": 0.0,
    }  # fmt: skip
    if _normalize_language(language) != "python" or (
        language_b is not None and _normalize_language(language_b) != "python"
    ):
        return none

    module = _import_optional("src.backend.engines.features.ast_normalizer")
    compare_robust = getattr(module, "compare_robust", None)
    if compare_robust is None:
        return none
    try:
        result = compare_robust(code_a, code_b)
    except Exception:
        _warn_once("ast_compare", "AST/CFG/PDG comparison failed; signal skipped")
        return none

    return {
        "similarity": _clamp01(result.get("similarity", 0.0)),
        "ast_sim": _clamp01(result.get("ast_sim", 0.0)),
        "cfg_sim": _clamp01(result.get("cfg_sim", 0.0)),
        "pdg_sim": _clamp01(result.get("pdg_sim", 0.0)),
        "available": 1.0,
    }


def _tfidf_similarity(code_a: str, code_b: str, language: str) -> float:
    """TF-IDF cosine score for a pair, with a pure-Python cosine fallback."""
    module = _import_optional("src.backend.engines.ml.tfidf_detector")
    detector_cls = getattr(module, "TFIDFSimilarityDetector", None)
    if detector_cls is not None:
        try:
            return _clamp01(
                detector_cls(language=language, ngram_size=3).score_pair(code_a, code_b)
            )
        except Exception:
            _warn_once("tfidf", "TF-IDF detector failed; using cosine fallback")
    return _cosine_similarity(
        _lexical_tokens(code_a, language), _lexical_tokens(code_b, language)
    )


def _cosine_similarity(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Cosine similarity over token-frequency vectors."""
    counts_a = _token_counts(tokens_a)
    counts_b = _token_counts(tokens_b)
    vocabulary = set(counts_a) | set(counts_b)
    if not vocabulary:
        return 1.0
    dot_product = sum(counts_a.get(t, 0) * counts_b.get(t, 0) for t in vocabulary)
    magnitude_a = sum(v * v for v in counts_a.values()) ** 0.5
    magnitude_b = sum(v * v for v in counts_b.values()) ** 0.5
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return _clamp01(dot_product / (magnitude_a * magnitude_b))


def _token_counts(tokens: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def _jaccard(tokens_a: Iterable[str], tokens_b: Iterable[str]) -> float:
    return _set_similarity(set(tokens_a), set(tokens_b))


def _ngrams(tokens: Sequence[str], size: int) -> set[tuple[str, ...]]:
    if size <= 0 or len(tokens) < size:
        return set()
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def _ngram_similarity(
    tokens_a: Sequence[str], tokens_b: Sequence[str], size: int
) -> float:
    ngrams_a = _ngrams(tokens_a, size)
    ngrams_b = _ngrams(tokens_b, size)
    if not ngrams_a and not ngrams_b:
        return _sequence_similarity(tokens_a, tokens_b)
    return _set_similarity(ngrams_a, ngrams_b)


def _winnowing_similarity(
    tokens_a: Sequence[str], tokens_b: Sequence[str], window: int = 4
) -> float:
    fingerprints_a = _winnow(tokens_a, window)
    fingerprints_b = _winnow(tokens_b, window)
    if not fingerprints_a and not fingerprints_b:
        return _sequence_similarity(tokens_a, tokens_b)
    return _set_similarity(fingerprints_a, fingerprints_b)


def _winnow(tokens: Sequence[str], window: int, size: int = 3) -> set[int]:
    """Real winnowing: keep the minimum k-gram hash of every window.

    The old version sampled every (window-1)-th k-gram *by position*, so one
    inserted token shifted the sampling grid and destroyed almost all matches.
    Hashes are content-based and deterministic (crc32, not the salted ``hash``).
    """
    size = min(size, len(tokens))
    if size == 0:
        return set()
    hashes = [
        zlib.crc32("\x1f".join(tokens[i : i + size]).encode("utf-8"))
        for i in range(len(tokens) - size + 1)
    ]
    window = max(1, window)
    if len(hashes) <= window:
        return {min(hashes)}
    return {min(hashes[i : i + window]) for i in range(len(hashes) - window + 1)}


_STRUCTURE_KEYS = {
    "functions": {"def", "function"},
    "classes": {"class"},
    "loops": {"for", "while"},
    "conditions": {"if", "elif", "else", "switch", "case"},
    "returns": {"return"},
}


def _structure_similarity(
    code_a: str,
    code_b: str,
    language_a: str = "python",
    language_b: str | None = None,
) -> float:
    """Compare counts of structural keywords (comments/strings excluded)."""

    def counts(code: str, language: str) -> dict[str, int]:
        tokens = _normalized_tokens(code, language)
        return {
            k: sum(1 for t in tokens if t in kws) for k, kws in _STRUCTURE_KEYS.items()
        }

    counts_a = counts(code_a, language_a)
    counts_b = counts(code_b, language_b or language_a)

    # Categories absent from both files carry no information. Counting them as
    # "identical" gave any two unrelated flat snippets a free ~0.6 here.
    scores = [
        1.0 - abs(counts_a[k] - counts_b[k]) / max(counts_a[k], counts_b[k])
        for k in counts_a
        if counts_a[k] or counts_b[k]
    ]
    return sum(scores) / len(scores) if scores else 1.0


def _sequence_similarity(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    # autojunk=False: with the default, any sequence >=200 tokens treats tokens
    # making up >1% of it as junk - i.e. `ID`, `(`, `)` - so ratios for real files
    # were badly underestimated.
    return SequenceMatcher(a=tokens_a, b=tokens_b, autojunk=False).ratio()
