"""Lightweight compatibility analyzer used by legacy integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import keyword
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


PYTHON_KEYWORDS = set(keyword.kwlist)
GENERIC_KEYWORDS = {
    "class",
    "const",
    "def",
    "else",
    "false",
    "for",
    "function",
    "if",
    "import",
    "in",
    "let",
    "none",
    "null",
    "return",
    "static",
    "true",
    "var",
    "while",
}


@dataclass
class CodeAnalysisResult:
    """Summary of a single source file analysis."""

    file_path: str
    language: str
    line_count: int
    token_count: int
    code_hash: str
    ai_detection: Dict[str, float | bool]
    complexity_metrics: Dict[str, int | float]


@dataclass
class CodeComparisonResult:
    """Pairwise similarity result."""

    file_a: str
    file_b: str
    overall_score: float
    individual_scores: Dict[str, float]
    is_suspicious: bool
    language_a: str
    language_b: str


class CodeAnalyzer:
    """Simple multi-signal analyzer compatible with the historic API."""

    def __init__(self, threshold: float = 0.5, enable_ai_detection: bool = True):
        self.threshold = threshold
        self.enable_ai_detection = enable_ai_detection

    def analyze_code(
        self,
        code: str,
        language: str,
        file_path: Optional[str] = None,
    ) -> CodeAnalysisResult:
        tokens = _lexical_tokens(code)
        line_count = (
            len([line for line in code.splitlines() if line.strip()])
            or len(code.splitlines())
            or 1
        )
        token_count = len(tokens)
        code_hash = sha256(code.encode("utf-8")).hexdigest()

        return CodeAnalysisResult(
            file_path=file_path or "<memory>",
            language=language,
            line_count=line_count,
            token_count=token_count,
            code_hash=code_hash,
            ai_detection=self._detect_ai(code),
            complexity_metrics={
                "line_count": line_count,
                "token_count": token_count,
                "function_count": len(re.findall(r"\b(def|function)\b", code)),
                "branch_count": len(
                    re.findall(r"\b(if|elif|else|for|while|match|case)\b", code)
                ),
            },
        )

    def compare_codes(
        self,
        code_a: str,
        code_b: str,
        language_a: str,
        language_b: str,
        file_a: Optional[str] = None,
        file_b: Optional[str] = None,
    ) -> CodeComparisonResult:
        normalized_a = _normalized_tokens(code_a, language_a)
        normalized_b = _normalized_tokens(code_b, language_b)

        token_score = _jaccard(normalized_a, normalized_b)
        ngram_score = _ngram_similarity(normalized_a, normalized_b, size=3)
        winnowing_score = _winnowing_similarity(normalized_a, normalized_b)
        structure_score = _structure_similarity(code_a, code_b)
        sequence_score = _sequence_similarity(normalized_a, normalized_b)
        normalization_graph_score = _normalization_graph_similarity(
            normalized_a, normalized_b
        )
        subsequence_merge_score = _merged_subsequence_similarity(
            normalized_a, normalized_b
        )
        tfidf_score = _tfidf_similarity(code_a, code_b, language_a)

        overall_score = (
            0.15 * token_score
            + 0.20 * ngram_score
            + 0.10 * winnowing_score
            + 0.15 * structure_score
            + 0.10 * sequence_score
            + 0.15 * normalization_graph_score
            + 0.10 * subsequence_merge_score
            + 0.05 * tfidf_score
        )
        overall_score = max(0.0, min(1.0, overall_score))

        scores = {
            "token_similarity": token_score,
            "ngram_similarity": ngram_score,
            "winnowing_similarity": winnowing_score,
            "structure_similarity": structure_score,
            "sequence_similarity": sequence_score,
            "normalization_graph_similarity": normalization_graph_score,
            "subsequence_merge_similarity": subsequence_merge_score,
            "tfidf_similarity": tfidf_score,
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
        self, submissions: Dict[str, str]
    ) -> List[CodeComparisonResult]:
        results: List[CodeComparisonResult] = []
        for file_a, file_b in combinations(sorted(submissions.keys()), 2):
            language_a = _detect_language(file_a, submissions[file_a])
            language_b = _detect_language(file_b, submissions[file_b])
            results.append(
                self.compare_codes(
                    submissions[file_a],
                    submissions[file_b],
                    language_a,
                    language_b,
                    file_a,
                    file_b,
                )
            )
        return results

    def find_suspicious_pairs(
        self,
        submissions: Dict[str, str],
        threshold: Optional[float] = None,
    ) -> List[CodeComparisonResult]:
        effective_threshold = self.threshold if threshold is None else threshold
        results = [
            result
            for result in self.analyze_pairwise(submissions)
            if result.overall_score >= effective_threshold
        ]
        return sorted(results, key=lambda result: result.overall_score, reverse=True)

    def _detect_ai(self, code: str) -> Dict[str, float | bool]:
        if not self.enable_ai_detection:
            return {"is_likely_ai": False, "ai_score": 0.0}

        model_result = _model_ai_detection(code)
        comment_lines = re.findall(r"^\s*#.*$", code, flags=re.MULTILINE)
        explanatory_comments = sum(
            1
            for line in comment_lines
            if re.search(
                r"\b(this|here|check|handle|calculate|return|function)\b", line.lower()
            )
        )
        repeated_indent = len(re.findall(r"^\s{4,}", code, flags=re.MULTILINE))
        heuristic_score = min(
            1.0,
            0.15 * explanatory_comments
            + 0.05 * repeated_indent
            + 0.02 * max(len(comment_lines) - 1, 0),
        )
        model_score = float(model_result.get("ai_probability", 0.0))
        score = max(heuristic_score, 0.65 * model_score + 0.35 * heuristic_score)
        return {
            "is_likely_ai": score >= 0.4,
            "ai_score": round(score, 3),
            "heuristic_ai_score": round(heuristic_score, 3),
            "model_ai_score": round(model_score, 3),
            "model_confidence": round(float(model_result.get("confidence", 0.0)), 3),
        }


def analyze_single_code(
    code: str,
    language: str,
    file_path: Optional[str] = None,
) -> CodeAnalysisResult:
    """Analyze a single snippet using default settings."""
    return CodeAnalyzer().analyze_code(code, language, file_path=file_path)


def compare_two_codes(
    code_a: str,
    code_b: str,
    language: str,
    *,
    file_a: Optional[str] = None,
    file_b: Optional[str] = None,
) -> CodeComparisonResult:
    """Compare two snippets using the same language for both sides."""
    return CodeAnalyzer().compare_codes(
        code_a,
        code_b,
        language,
        language,
        file_a=file_a,
        file_b=file_b,
    )


def _detect_language(name: str, code: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix == ".java":
        return "java"
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return "javascript"
    if re.search(r"\bdef\b.*:", code):
        return "python"
    if re.search(r"\bfunction\b", code):
        return "javascript"
    return "python"


def _strip_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
    return code


def _lexical_tokens(code: str) -> List[str]:
    return re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|[^\s]", _strip_comments(code))


def _normalized_tokens(code: str, language: str) -> List[str]:
    normalized: List[str] = []
    tokens = _lexical_tokens(code)
    keyword_set = GENERIC_KEYWORDS | (
        PYTHON_KEYWORDS if language == "python" else set()
    )

    for token in tokens:
        if re.fullmatch(r"[A-Za-z_]\w*", token):
            lowered = token.lower()
            normalized.append(lowered if lowered in keyword_set else "ID")
        elif re.fullmatch(r"\d+", token):
            normalized.append("NUM")
        elif token.startswith(("'", '"')):
            normalized.append("STR")
        else:
            normalized.append(token)
    return normalized


def _normalization_graph_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Compare normalized token transition graphs for obfuscation-resistant similarity."""
    nodes_a, edges_a = _token_normalization_graph(tokens_a)
    nodes_b, edges_b = _token_normalization_graph(tokens_b)

    node_score = _set_similarity(nodes_a, nodes_b)
    edge_score = _set_similarity(edges_a, edges_b)
    if not nodes_a and not nodes_b:
        return 1.0
    return 0.35 * node_score + 0.65 * edge_score


def _token_normalization_graph(
    tokens: List[str],
) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """Build a compact graph from canonical token categories and local transitions."""
    canonical = [_canonical_graph_token(token) for token in tokens]
    nodes = set(canonical)
    edges = {
        (canonical[index], canonical[index + 1]) for index in range(len(canonical) - 1)
    }
    return nodes, edges


def _canonical_graph_token(token: str) -> str:
    """Map normalized tokens into stable graph labels."""
    if token in {"ID", "NUM", "STR"}:
        return token
    if token in {"def", "function", "class", "return", "if", "else", "for", "while"}:
        return f"KW:{token}"
    if re.fullmatch(r"[+\-*/%]=?|==|!=|<=|>=|<|>|&&|\|\|", token):
        return "OP"
    if token in {"(", ")", "[", "]", "{", "}", ":", ";", ","}:
        return f"PUNC:{token}"
    return token


def _merged_subsequence_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Score copied subsequences after merging matches split by small obfuscating edits."""
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    blocks = [
        (block.a, block.b, block.size)
        for block in SequenceMatcher(
            a=tokens_a, b=tokens_b, autojunk=False
        ).get_matching_blocks()
        if block.size > 0
    ]
    if not blocks:
        return 0.0

    merged: List[Tuple[int, int, int]] = []
    for start_a, start_b, size in blocks:
        if not merged:
            merged.append((start_a, start_b, size))
            continue

        prev_a, prev_b, prev_size = merged[-1]
        gap_a = start_a - (prev_a + prev_size)
        gap_b = start_b - (prev_b + prev_size)
        if 0 <= gap_a <= 3 and 0 <= gap_b <= 3:
            merged[-1] = (prev_a, prev_b, start_a + size - prev_a)
        else:
            merged.append((start_a, start_b, size))

    matched_a = sum(size for _, _, size in merged)
    matched_b = matched_a
    coverage_a = matched_a / len(tokens_a)
    coverage_b = matched_b / len(tokens_b)
    if coverage_a + coverage_b == 0:
        return 0.0
    return 2 * coverage_a * coverage_b / (coverage_a + coverage_b)


def _set_similarity(items_a: Set[object], items_b: Set[object]) -> float:
    """Return Jaccard similarity for two sets, treating two empty sets as identical."""
    if not items_a and not items_b:
        return 1.0
    return len(items_a & items_b) / len(items_a | items_b)


def _model_ai_detection(code: str) -> Dict[str, float | bool]:
    """Run the existing model-backed AI detector when its dependencies are available."""
    try:
        from src.backend.engines.similarity.ai_detection import AIDetectionEngine

        result = AIDetectionEngine().analyze(code)
        return {
            "ai_probability": float(result.get("ai_probability", 0.0)),
            "confidence": float(result.get("confidence", 0.0)),
        }
    except Exception:
        return {"ai_probability": 0.0, "confidence": 0.0}


def _tfidf_similarity(code_a: str, code_b: str, language: str) -> float:
    """Compute a lightweight TF-IDF/cosine baseline score for a code pair."""
    try:
        from src.backend.engines.ml.tfidf_detector import TFIDFSimilarityDetector

        detector = TFIDFSimilarityDetector(language=language, ngram_size=3)
        return detector.score_pair(code_a, code_b)
    except Exception:
        return _cosine_similarity(_lexical_tokens(code_a), _lexical_tokens(code_b))


def _cosine_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Return cosine similarity over simple token-frequency vectors."""
    counts_a = _token_counts(tokens_a)
    counts_b = _token_counts(tokens_b)
    vocabulary = set(counts_a) | set(counts_b)
    if not vocabulary:
        return 1.0

    dot_product = sum(
        counts_a.get(token, 0) * counts_b.get(token, 0) for token in vocabulary
    )
    magnitude_a = sum(value * value for value in counts_a.values()) ** 0.5
    magnitude_b = sum(value * value for value in counts_b.values()) ** 0.5
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot_product / (magnitude_a * magnitude_b)))


def _token_counts(tokens: List[str]) -> Dict[str, int]:
    """Count tokens without importing heavier collection helpers."""
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def _jaccard(tokens_a: Iterable[str], tokens_b: Iterable[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)


def _ngrams(tokens: List[str], size: int) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return set()
    return {
        tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)
    }


def _ngram_similarity(tokens_a: List[str], tokens_b: List[str], size: int) -> float:
    ngrams_a = _ngrams(tokens_a, size)
    ngrams_b = _ngrams(tokens_b, size)
    if not ngrams_a and not ngrams_b:
        return _sequence_similarity(tokens_a, tokens_b)
    return len(ngrams_a & ngrams_b) / len(ngrams_a | ngrams_b)


def _winnowing_similarity(
    tokens_a: List[str], tokens_b: List[str], window: int = 4
) -> float:
    fingerprints_a = _winnow(tokens_a, window)
    fingerprints_b = _winnow(tokens_b, window)
    if not fingerprints_a and not fingerprints_b:
        return _sequence_similarity(tokens_a, tokens_b)
    return len(fingerprints_a & fingerprints_b) / len(fingerprints_a | fingerprints_b)


def _winnow(tokens: List[str], window: int) -> set[tuple[str, ...]]:
    fingerprints: set[tuple[str, ...]] = set()
    size = min(3, len(tokens)) if tokens else 0
    grams = list(_ngrams(tokens, size)) if size else []
    if not grams:
        return fingerprints
    for index in range(0, len(grams), max(1, window - 1)):
        fingerprints.add(grams[index])
    return fingerprints


def _structure_similarity(code_a: str, code_b: str) -> float:
    def counts(code: str) -> Dict[str, int]:
        lowered = code.lower()
        return {
            "functions": len(re.findall(r"\b(def|function)\b", lowered)),
            "classes": len(re.findall(r"\bclass\b", lowered)),
            "loops": len(re.findall(r"\b(for|while)\b", lowered)),
            "conditions": len(re.findall(r"\b(if|elif|else|switch|case)\b", lowered)),
            "returns": len(re.findall(r"\breturn\b", lowered)),
        }

    counts_a = counts(code_a)
    counts_b = counts(code_b)
    total = 0.0
    for key, value_a in counts_a.items():
        value_b = counts_b[key]
        baseline = max(value_a, value_b, 1)
        total += 1.0 - abs(value_a - value_b) / baseline
    return total / len(counts_a)


def _sequence_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    return SequenceMatcher(a=tokens_a, b=tokens_b).ratio()
