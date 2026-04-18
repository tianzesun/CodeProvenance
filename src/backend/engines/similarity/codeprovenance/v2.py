"""
CodeProvenance Engine v2.

Token + AST hybrid similarity combining token-based and structural analysis.
This version adds AST-based comparison for better structural understanding.
"""

from typing import Dict, Any, List, Optional
from .base import BaseCodeProvenanceEngine
from .version_registry import register_engine


@register_engine("codeprovenance:v2")
class CodeProvenanceV2(BaseCodeProvenanceEngine):
    """Version 2: Token + AST hybrid similarity.

    Features:
    - Token-based similarity (Jaccard + n-gram)
    - AST structural similarity
    - Weighted combination of metrics
    - Better detection of renamed variables

    Improvements over v1:
    - Detects structural similarities despite renaming
    - Better precision for Type-2 clones
    - More robust to formatting changes

    Use cases:
    - Academic plagiarism detection
    - Code review assistance
    - Structural similarity analysis
    """

    def __init__(
        self,
        token_weight: float = 0.4,
        ast_weight: float = 0.6,
        ngram_size: int = 3,
    ):
        """Initialize v2 engine.

        Args:
            token_weight: Weight for token similarity (default: 0.4)
            ast_weight: Weight for AST similarity (default: 0.6)
            ngram_size: Size of n-grams for token comparison (default: 3)
        """
        self._token_weight = token_weight
        self._ast_weight = ast_weight
        self._ngram_size = ngram_size

        # Validate weights
        if abs(token_weight + ast_weight - 1.0) > 0.01:
            raise ValueError("Weights must sum to 1.0")

    @property
    def version(self) -> str:
        """Engine version identifier."""
        return "codeprovenance:v2"

    @property
    def name(self) -> str:
        """Human-readable engine name."""
        return "CodeProvenance v2 (Token + AST)"

    @property
    def description(self) -> str:
        """Engine description."""
        return "Token + AST hybrid similarity for structural analysis"

    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        """Compare two code snippets.

        Args:
            code_a: First code snippet
            code_b: Second code snippet
            **kwargs: Additional parameters
                - language: Programming language (default: auto-detect)

        Returns:
            Similarity score in [0.0, 1.0]
        """
        language = kwargs.get("language", self._detect_language(code_a))

        # Calculate token similarity
        token_score = self._token_similarity(code_a, code_b)

        # Calculate AST similarity
        ast_score = self._ast_similarity(code_a, code_b, language)

        # Weighted combination
        return self._token_weight * token_score + self._ast_weight * ast_score

    def _token_similarity(self, code_a: str, code_b: str) -> float:
        """Calculate token-based similarity (from v1)."""
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        # Jaccard similarity
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        jaccard_score = intersection / union if union > 0 else 0.0

        # N-gram similarity
        if len(tokens_a) >= self._ngram_size and len(tokens_b) >= self._ngram_size:
            ngrams_a = self._get_ngrams(tokens_a)
            ngrams_b = self._get_ngrams(tokens_b)
            ngram_intersection = len(ngrams_a.intersection(ngrams_b))
            ngram_union = len(ngrams_a.union(ngrams_b))
            ngram_score = ngram_intersection / ngram_union if ngram_union > 0 else 0.0
        else:
            ngram_score = jaccard_score

        return 0.6 * jaccard_score + 0.4 * ngram_score

    def _ast_similarity(self, code_a: str, code_b: str, language: str) -> float:
        """Calculate AST-based structural similarity."""
        try:
            # Try to use the IR layer
            from src.backend.core.ir.ast_ir import ASTIR

            ast_a = ASTIR.from_source(code_a, language)
            ast_b = ASTIR.from_source(code_b, language)

            # Compare AST structure
            return self._compare_ast_nodes(ast_a.root, ast_b.root)
        except Exception:
            # Fallback: use simple structural comparison
            return self._simple_structural_similarity(code_a, code_b)

    def _compare_ast_nodes(self, node_a, node_b) -> float:
        """Recursively compare AST nodes."""
        if node_a is None and node_b is None:
            return 1.0
        if node_a is None or node_b is None:
            return 0.0

        # Compare node types
        if node_a.node_type != node_b.node_type:
            return 0.0

        # Compare children
        if len(node_a.children) != len(node_b.children):
            return 0.0

        if not node_a.children:
            # Leaf nodes - compare values (normalized)
            val_a = self._normalize_value(node_a.value)
            val_b = self._normalize_value(node_b.value)
            return 1.0 if val_a == val_b else 0.0

        # Compare children recursively
        child_scores = []
        for child_a, child_b in zip(node_a.children, node_b.children):
            child_scores.append(self._compare_ast_nodes(child_a, child_b))

        return sum(child_scores) / len(child_scores) if child_scores else 1.0

    def _normalize_value(self, value: str) -> str:
        """Normalize value for comparison."""
        # Normalize identifiers
        if value and value[0].isalpha():
            return "ID"
        # Normalize literals
        if value.isdigit():
            return "NUM"
        if value.startswith('"') or value.startswith("'"):
            return "STR"
        return value

    def _simple_structural_similarity(self, code_a: str, code_b: str) -> float:
        """Simple structural similarity fallback."""

        # Count structural elements
        def count_elements(code: str) -> Dict[str, int]:
            import re

            return {
                "functions": len(re.findall(r"\bdef\b|\bfunction\b", code)),
                "classes": len(re.findall(r"\bclass\b", code)),
                "loops": len(re.findall(r"\bfor\b|\bwhile\b", code)),
                "conditions": len(re.findall(r"\bif\b|\belse\b", code)),
            }

        elements_a = count_elements(code_a)
        elements_b = count_elements(code_b)

        # Calculate similarity
        total_diff = 0
        total_count = 0

        for key in elements_a:
            count_a = elements_a[key]
            count_b = elements_b.get(key, 0)
            total_diff += abs(count_a - count_b)
            total_count += max(count_a, count_b)

        if total_count == 0:
            return 1.0

        return 1.0 - (total_diff / total_count)

    def _tokenize(self, code: str) -> List[str]:
        """Tokenize source code."""
        import re

        # Remove comments
        code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)

        # Remove strings
        code = re.sub(r'["\'].*?["\']', "STR", code, flags=re.DOTALL)

        # Tokenize
        tokens = re.findall(r"[a-zA-Z_]\w*|[0-9]+|[+\-*/%=<>&|^~!?:;,.()\[\]{}]", code)

        return [t for t in tokens if t]

    def _get_ngrams(self, tokens: List[str]) -> set:
        """Extract n-grams from token sequence."""
        ngrams = set()
        for i in range(len(tokens) - self._ngram_size + 1):
            ngram = " ".join(tokens[i : i + self._ngram_size])
            ngrams.add(ngram)
        return ngrams

    def _detect_language(self, code: str) -> str:
        """Simple language detection."""
        import re

        if re.search(r"\bdef\b.*:", code):
            return "python"
        if re.search(r"\bpublic\s+(static\s+)?void\b", code):
            return "java"
        if re.search(r"\bfunction\b.*{", code):
            return "javascript"

        return "unknown"

    def get_config(self) -> Dict[str, Any]:
        """Get engine configuration."""
        config = super().get_config()
        config.update(
            {
                "token_weight": self._token_weight,
                "ast_weight": self._ast_weight,
                "ngram_size": self._ngram_size,
                "algorithm": "token + ast hybrid",
                "improvements": [
                    "Structural similarity detection",
                    "Better Type-2 clone detection",
                    "Renamed variable handling",
                ],
            }
        )
        return config
