"""
CodeProvenance Engine v3.

Advanced graph-based similarity with semantic understanding.
This version adds graph-based comparison and semantic analysis.
"""

from typing import Dict, Any, List, Optional, Set
from .base import BaseCodeProvenanceEngine
from .version_registry import register_engine


@register_engine("codeprovenance:v3")
class CodeProvenanceV3(BaseCodeProvenanceEngine):
    """Version 3: Advanced graph-based similarity.

    Features:
    - Token-based similarity (Jaccard + n-gram)
    - AST structural similarity
    - Graph-based call/dependency analysis
    - Semantic similarity using embeddings
    - Multi-language support

    Improvements over v2:
    - Graph-based structural analysis
    - Semantic understanding of code
    - Better cross-language detection
    - Handles complex refactorings

    Use cases:
    - Research benchmarking
    - Cross-language similarity
    - Semantic clone detection
    - Advanced forensics analysis
    """

    def __init__(
        self,
        token_weight: float = 0.25,
        ast_weight: float = 0.35,
        graph_weight: float = 0.25,
        semantic_weight: float = 0.15,
        ngram_size: int = 3,
        use_embeddings: bool = False,
    ):
        """Initialize v3 engine.

        Args:
            token_weight: Weight for token similarity (default: 0.25)
            ast_weight: Weight for AST similarity (default: 0.35)
            graph_weight: Weight for graph similarity (default: 0.25)
            semantic_weight: Weight for semantic similarity (default: 0.15)
            ngram_size: Size of n-grams for token comparison (default: 3)
            use_embeddings: Whether to use embedding models (default: False)
        """
        self._token_weight = token_weight
        self._ast_weight = ast_weight
        self._graph_weight = graph_weight
        self._semantic_weight = semantic_weight
        self._ngram_size = ngram_size
        self._use_embeddings = use_embeddings

        # Validate weights
        total = token_weight + ast_weight + graph_weight + semantic_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

        # Lazy-load embedding model if needed
        self._embedding_model = None

    @property
    def version(self) -> str:
        """Engine version identifier."""
        return "codeprovenance:v3"

    @property
    def name(self) -> str:
        """Human-readable engine name."""
        return "CodeProvenance v3 (Advanced Graph)"

    @property
    def description(self) -> str:
        """Engine description."""
        return "Advanced graph-based similarity with semantic understanding"

    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        """Compare two code snippets.

        Args:
            code_a: First code snippet
            code_b: Second code snippet
            **kwargs: Additional parameters
                - language_a: Language of first snippet (default: auto-detect)
                - language_b: Language of second snippet (default: auto-detect)

        Returns:
            Similarity score in [0.0, 1.0]
        """
        language_a = kwargs.get("language_a", self._detect_language(code_a))
        language_b = kwargs.get("language_b", self._detect_language(code_b))

        # Calculate all similarity metrics
        token_score = self._token_similarity(code_a, code_b)
        ast_score = self._ast_similarity(code_a, code_b, language_a, language_b)
        graph_score = self._graph_similarity(code_a, code_b, language_a, language_b)
        semantic_score = self._semantic_similarity(code_a, code_b)

        # Weighted combination
        return (
            self._token_weight * token_score
            + self._ast_weight * ast_score
            + self._graph_weight * graph_score
            + self._semantic_weight * semantic_score
        )

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

    def _ast_similarity(
        self, code_a: str, code_b: str, lang_a: str, lang_b: str
    ) -> float:
        """Calculate AST-based structural similarity (from v2)."""
        try:
            from src.backend.core.ir.ast_ir import ASTIR

            ast_a = ASTIR.from_source(code_a, lang_a)
            ast_b = ASTIR.from_source(code_b, lang_b)

            return self._compare_ast_nodes(ast_a.root, ast_b.root)
        except Exception:
            return self._simple_structural_similarity(code_a, code_b)

    def _compare_ast_nodes(self, node_a, node_b) -> float:
        """Recursively compare AST nodes."""
        if node_a is None and node_b is None:
            return 1.0
        if node_a is None or node_b is None:
            return 0.0

        if node_a.node_type != node_b.node_type:
            return 0.0

        if len(node_a.children) != len(node_b.children):
            return 0.0

        if not node_a.children:
            val_a = self._normalize_value(node_a.value)
            val_b = self._normalize_value(node_b.value)
            return 1.0 if val_a == val_b else 0.0

        child_scores = []
        for child_a, child_b in zip(node_a.children, node_b.children):
            child_scores.append(self._compare_ast_nodes(child_a, child_b))

        return sum(child_scores) / len(child_scores) if child_scores else 1.0

    def _graph_similarity(
        self, code_a: str, code_b: str, lang_a: str, lang_b: str
    ) -> float:
        """Calculate graph-based structural similarity."""
        try:
            from src.backend.core.ir.graph_ir import GraphIR

            graph_a = GraphIR.from_source(code_a, lang_a)
            graph_b = GraphIR.from_source(code_b, lang_b)

            return self._compare_graphs(graph_a, graph_b)
        except Exception:
            return 0.5  # Fallback to neutral score

    def _compare_graphs(self, graph_a, graph_b) -> float:
        """Compare two graph IRs."""
        # Compare node types
        types_a = set(node.node_type for node in graph_a.nodes)
        types_b = set(node.node_type for node in graph_b.nodes)

        if not types_a and not types_b:
            return 1.0

        type_intersection = len(types_a.intersection(types_b))
        type_union = len(types_a.union(types_b))
        type_score = type_intersection / type_union if type_union > 0 else 0.0

        # Compare edge types
        edge_types_a = set(edge.edge_type for edge in graph_a.edges)
        edge_types_b = set(edge.edge_type for edge in graph_b.edges)

        if not edge_types_a and not edge_types_b:
            edge_score = 1.0
        else:
            edge_intersection = len(edge_types_a.intersection(edge_types_b))
            edge_union = len(edge_types_a.union(edge_types_b))
            edge_score = edge_intersection / edge_union if edge_union > 0 else 0.0

        # Compare node counts (normalized)
        count_a = len(graph_a.nodes)
        count_b = len(graph_b.nodes)
        max_count = max(count_a, count_b)
        count_score = 1.0 - abs(count_a - count_b) / max_count if max_count > 0 else 1.0

        # Weighted combination
        return 0.4 * type_score + 0.3 * edge_score + 0.3 * count_score

    def _semantic_similarity(self, code_a: str, code_b: str) -> float:
        """Calculate semantic similarity using embeddings."""
        if not self._use_embeddings:
            # Fallback: use comment/docstring similarity
            return self._comment_similarity(code_a, code_b)

        try:
            # Lazy-load embedding model
            if self._embedding_model is None:
                self._load_embedding_model()

            # Generate embeddings
            embedding_a = self._embedding_model.encode(code_a)
            embedding_b = self._embedding_model.encode(code_b)

            # Calculate cosine similarity
            return self._cosine_similarity(embedding_a, embedding_b)
        except Exception:
            return self._comment_similarity(code_a, code_b)

    def _load_embedding_model(self):
        """Load embedding model (lazy loading)."""
        try:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            self._embedding_model = None

    def _cosine_similarity(self, vec_a, vec_b) -> float:
        """Calculate cosine similarity between two vectors."""
        import numpy as np

        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _comment_similarity(self, code_a: str, code_b: str) -> float:
        """Similarity based on comments/docstrings."""
        import re

        # Extract comments
        comments_a = set(re.findall(r"#.*|//.*|/\*.*?\*/", code_a, re.DOTALL))
        comments_b = set(re.findall(r"#.*|//.*|/\*.*?\*/", code_b, re.DOTALL))

        # Clean comments
        def clean(comments: Set[str]) -> Set[str]:
            cleaned = set()
            for comment in comments:
                # Remove comment markers
                comment = re.sub(r"^[#/]+\s*", "", comment)
                comment = re.sub(r"\*/$", "", comment)
                # Normalize whitespace
                comment = " ".join(comment.split())
                if comment:
                    cleaned.add(comment.lower())
            return cleaned

        clean_a = clean(comments_a)
        clean_b = clean(comments_b)

        if not clean_a and not clean_b:
            return 1.0

        intersection = len(clean_a.intersection(clean_b))
        union = len(clean_a.union(clean_b))

        return intersection / union if union > 0 else 0.0

    def _normalize_value(self, value: str) -> str:
        """Normalize value for comparison."""
        if value and value[0].isalpha():
            return "ID"
        if value.isdigit():
            return "NUM"
        if value.startswith('"') or value.startswith("'"):
            return "STR"
        return value

    def _simple_structural_similarity(self, code_a: str, code_b: str) -> float:
        """Simple structural similarity fallback."""

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

        code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
        code = re.sub(r'["\'].*?["\']', "STR", code, flags=re.DOTALL)

        tokens = re.findall(r"[a-zA-Z_]\w*|[0-9]+|[+\-*/%=<>&|^~!?:;,.()\[\]{}]", code)

        return [t for t in tokens if t]

    def _get_ngrams(self, tokens: List[str]) -> Set[str]:
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
                "graph_weight": self._graph_weight,
                "semantic_weight": self._semantic_weight,
                "ngram_size": self._ngram_size,
                "use_embeddings": self._use_embeddings,
                "algorithm": "token + ast + graph + semantic",
                "improvements": [
                    "Graph-based structural analysis",
                    "Semantic understanding",
                    "Cross-language detection",
                    "Complex refactoring handling",
                ],
            }
        )
        return config
