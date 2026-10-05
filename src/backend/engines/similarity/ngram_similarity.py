"""
N-gram based similarity algorithm.

Compares code based on character or token n-grams.
"""

import re
from functools import lru_cache
from typing import Any

from .base_similarity import BaseSimilarityAlgorithm
from .code_scan import normalized_text


def _token_values(tokens: Any) -> list[str]:
    """Token strings from a list of strings or ``{"value": ...}`` dicts."""
    values: list[str] = []
    for token in tokens or []:
        value = token.get("value", "") if isinstance(token, dict) else token
        if value is not None and str(value) != "":
            values.append(str(value))
    return values


@lru_cache(maxsize=64)
def _char_ngram_hashes(text: str, n: int) -> frozenset[int]:
    """Hashes of the distinct character n-grams of ``text`` (cached per file).

    Every pair re-derived each file's n-grams. Hashing them (instead of keeping the
    substrings) keeps the cached sets small.
    """
    if len(text) < n:
        return frozenset([hash(text)]) if text else frozenset()
    return frozenset(hash(text[i : i + n]) for i in range(len(text) - n + 1))


class NgramSimilarity(BaseSimilarityAlgorithm):
    """
    N-gram similarity algorithm that compares code based on character n-grams.

    Effective for detecting similar code despite whitespace changes, comment edits, etc.
    """

    def __init__(self, n: int = 5):
        super().__init__("ngram")
        if n < 1:
            raise ValueError("n must be at least 1")
        self.n = n

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on n-gram similarity.

        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation

        Returns:
            Similarity score between 0.0 and 1.0
        """
        content_a = self._get_content_for_ngrams(parsed_a)
        content_b = self._get_content_for_ngrams(parsed_b)

        if not content_a and not content_b:
            return 1.0
        if not content_a or not content_b:
            return 0.0

        set_a = _char_ngram_hashes(content_a, self.n)
        set_b = _char_ngram_hashes(content_b, self.n)

        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0

        # Sørensen–Dice coefficient of the n-gram sets
        total = len(set_a) + len(set_b)
        return (2.0 * len(set_a & set_b)) / total if total else 0.0

    def _get_content_for_ngrams(self, parsed: dict[str, Any]) -> str:
        """
        Extract content suitable for n-gram analysis.

        Comments are dropped and string/number literals normalised with a
        comment-and-string-aware scanner. The earlier regex chain
        (``["'].*?["']`` with DOTALL) let an apostrophe in a comment pair with the
        next quote far below it and erase all the code in between.

        Args:
            parsed: Parsed code representation

        Returns:
            String content for n-gram generation
        """
        tokens = parsed.get("tokens")
        if tokens:
            content = " ".join(_token_values(tokens))
            content = re.sub(r"\b\d+(\.\d+)?\b", "NUM", content)
            return content
        raw = parsed.get("raw", "")
        return normalized_text(raw, parsed.get("language")) if raw else ""

    def _get_ngrams(self, text: str, n: int) -> list[str]:
        """
        Generate n-grams from text.

        Args:
            text: Input text
            n: Size of n-grams

        Returns:
            List of n-grams
        """
        if len(text) < n:
            return [text] if text else []
        return [text[i : i + n] for i in range(len(text) - n + 1)]


class TokenNgramSimilarity(BaseSimilarityAlgorithm):
    """
    Token n-gram similarity algorithm.

    Creates n-grams from token sequences rather than characters.
    """

    def __init__(self, n: int = 2):
        super().__init__("token_ngram")
        if n < 1:
            raise ValueError("n must be at least 1")
        self.n = n

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on token n-gram similarity.

        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation

        Returns:
            Similarity score between 0.0 and 1.0
        """
        tokens_a = _token_values(parsed_a.get("tokens", []))
        tokens_b = _token_values(parsed_b.get("tokens", []))

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        set_a = {tuple(g) for g in self._get_token_ngrams(tokens_a, self.n)}
        set_b = {tuple(g) for g in self._get_token_ngrams(tokens_b, self.n)}

        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0

        # Sørensen–Dice coefficient of token n-gram sets
        total = len(set_a) + len(set_b)
        return (2.0 * len(set_a & set_b)) / total if total else 0.0

    def _get_token_ngrams(self, tokens: list[str], n: int) -> list[list[str]]:
        """
        Generate token n-grams from token list.

        Args:
            tokens: List of tokens
            n: Size of n-grams

        Returns:
            List of token n-grams (each n-gram is a list of tokens)
        """
        if len(tokens) < n:
            return [tokens] if tokens else []
        return [tokens[i : i + n] for i in range(len(tokens) - n + 1)]
