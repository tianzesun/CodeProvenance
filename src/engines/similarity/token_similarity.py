"""
Enhanced Token-based similarity algorithm.

Compares code based on token sequences using:
- Jaccard similarity of token sets
- Longest Common Subsequence (LCS)
- N-gram sequence similarity
- Token type distribution
- Keyword overlap detection
"""

import logging
import re
from typing import List, Dict, Any, Set, Tuple
from .base_similarity import BaseSimilarityAlgorithm
from collections import Counter
import math

logger = logging.getLogger(__name__)


class TokenSimilarity(BaseSimilarityAlgorithm):
    """
    Enhanced Token similarity algorithm that compares code based on token sequences.

    Uses multiple token-based metrics:
    - Jaccard similarity of token sets
    - N-gram overlap
    - Token type distribution
    - Keyword overlap

    Tokenization results are cached by content hash so the same file is only
    tokenized once regardless of how many pairs it participates in.
    """

    def __init__(
        self,
        jaccard_weight: float = 0.4,
        ngram_weight: float = 0.3,
        distribution_weight: float = 0.2,
        keyword_weight: float = 0.1,
        ngram_size: int = 3,
    ) -> None:
        """Initialize Token similarity algorithm."""
        super().__init__("enhanced_token")
        self.jaccard_weight = jaccard_weight
        self.ngram_weight = ngram_weight
        self.distribution_weight = distribution_weight
        self.keyword_weight = keyword_weight
        self.ngram_size = ngram_size

        # Token cache keyed by raw code SHA-256 (avoids re-tokenizing same file)
        from src.engines.cache import TokenCache
        self._token_cache = TokenCache(maxsize=8192)

        # Programming language keywords
        self.keywords: Set[str] = {
            "if", "else", "elif", "for", "while", "do", "switch", "case",
            "break", "continue", "return", "try", "except", "catch", "finally",
            "throw", "throws", "raise", "yield", "await", "async",
            "class", "def", "func", "function", "import", "from", "package",
            "struct", "interface", "enum", "type", "trait", "impl",
            "true", "false", "null", "nil", "None", "undefined", "NaN",
            "and", "or", "not", "in", "is", "instanceof", "typeof",
            "var", "let", "const", "auto", "static", "final",
            "public", "private", "protected", "internal", "abstract",
            "virtual", "override", "new", "delete", "this", "self",
            "super", "base", "extends", "implements", "with",
        }

    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """Compare two parsed code representations based on token similarity.

        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation

        Returns:
            Similarity score between 0.0 and 1.0
        """
        tokens_a = self._extract_tokens(parsed_a)
        tokens_b = self._extract_tokens(parsed_b)

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        jaccard_score = self._jaccard_similarity(tokens_a, tokens_b)
        ngram_score = self._ngram_similarity(tokens_a, tokens_b)
        distribution_score = self._distribution_similarity(tokens_a, tokens_b)
        keyword_score = self._keyword_similarity(tokens_a, tokens_b)

        final_score = (
            jaccard_score * self.jaccard_weight
            + ngram_score * self.ngram_weight
            + distribution_score * self.distribution_weight
            + keyword_score * self.keyword_weight
        )

        return min(1.0, max(0.0, final_score))

    # ── Token extraction (cached) ──────────────────────────────────────

    def _extract_tokens(self, parsed: Dict[str, Any]) -> List[str]:
        """Extract token values from parsed representation."""
        if "tokens" in parsed:
            tokens = parsed["tokens"]
            if tokens and isinstance(tokens[0], dict):
                return [t.get("value", "") for t in tokens if t.get("value")]
            return [str(t) for t in tokens]
        if "raw" in parsed:
            raw = parsed["raw"]
            return self._token_cache.get_or_compute(raw, self._tokenize_cached)
        return []

    def _tokenize_cached(self, text: str) -> List[str]:
        """Tokenize source code text (called by cache on misses)."""
        # Remove strings and comments
        text = re.sub(r'["\'].*?["\']', 'STR', text, flags=re.DOTALL)
        text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        text = re.sub(r'#.*?$', '', text, flags=re.MULTILINE)

        # Tokenize
        tokens = re.findall(
            r'[a-zA-Z_]\w*|[0-9]+|[+\-*/%=<>&|^~!?:;,.()\[\]{}]', text
        )
        return [t for t in tokens if t]

    # ── Metrics ─────────────────────────────────────────────────────────

    def _jaccard_similarity(self, tokens_a: List[str], tokens_b: List[str]) -> float:
        """Calculate Jaccard similarity of token sets."""
        set_a = set(tokens_a)
        set_b = set(tokens_b)

        if not set_a and not set_b:
            return 1.0

        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))

        return intersection / union if union > 0 else 0.0

    def _ngram_similarity(self, tokens_a: List[str], tokens_b: List[str]) -> float:
        """Calculate n-gram overlap similarity."""
        if len(tokens_a) < self.ngram_size or len(tokens_b) < self.ngram_size:
            return self._jaccard_similarity(tokens_a, tokens_b)

        ngrams_a = self._get_ngrams(tokens_a)
        ngrams_b = self._get_ngrams(tokens_b)

        if not ngrams_a and not ngrams_b:
            return 1.0

        intersection = len(ngrams_a.intersection(ngrams_b))
        union = len(ngrams_a.union(ngrams_b))

        return intersection / union if union > 0 else 0.0

    def _get_ngrams(self, tokens: List[str]) -> Set[str]:
        """Extract n-grams from token sequence."""
        ngrams: Set[str] = set()
        for i in range(len(tokens) - self.ngram_size + 1):
            ngram = " ".join(tokens[i : i + self.ngram_size])
            ngrams.add(ngram)
        return ngrams

    def _distribution_similarity(self, tokens_a: List[str], tokens_b: List[str]) -> float:
        """Calculate similarity based on token type distributions."""
        dist_a = self._get_token_distribution(tokens_a)
        dist_b = self._get_token_distribution(tokens_b)

        common_keys = set(dist_a.keys()).union(set(dist_b.keys()))

        if not common_keys:
            return 1.0

        dot_product = sum(dist_a.get(k, 0) * dist_b.get(k, 0) for k in common_keys)
        norm_a = math.sqrt(sum(v ** 2 for v in dist_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in dist_b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _get_token_distribution(self, tokens: List[str]) -> Dict[str, float]:
        """Get distribution of token types."""
        categories: Dict[str, int] = {
            "identifier": 0,
            "keyword": 0,
            "literal": 0,
            "operator": 0,
            "punctuation": 0,
        }

        operators = set("+-*/%=<>&|^~!")
        punctuation = set("()[]{}:;,.")

        for token in tokens:
            if token in self.keywords:
                categories["keyword"] += 1
            elif token[0].isdigit():
                categories["literal"] += 1
            elif token in operators or len(token) == 1:
                categories["punctuation"] += 1
            elif any(c in token for c in operators):
                categories["operator"] += 1
            else:
                categories["identifier"] += 1

        total = sum(categories.values())
        if total == 0:
            return {k: 0.0 for k in categories}

        return {k: v / total for k, v in categories.items()}

    def _keyword_similarity(self, tokens_a: List[str], tokens_b: List[str]) -> float:
        """Calculate similarity based on keyword overlap."""
        keywords_a = {t.lower() for t in tokens_a if t.lower() in self.keywords}
        keywords_b = {t.lower() for t in tokens_b if t.lower() in self.keywords}

        if not keywords_a and not keywords_b:
            return 1.0

        intersection = len(keywords_a.intersection(keywords_b))
        union = len(keywords_a.union(keywords_b))

        return intersection / union if union > 0 else 0.0