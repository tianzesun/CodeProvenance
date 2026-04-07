"""
N-gram based similarity algorithm.

Compares code based on character or token n-grams.
"""

from typing import List, Dict, Any, Set
from .base_similarity import BaseSimilarityAlgorithm
import re


class NgramSimilarity(BaseSimilarityAlgorithm):
    """
    N-gram similarity algorithm that compares code based on character n-grams.

    Effective for detecting similar code despite whitespace changes, renaming, etc.
    """

    def __init__(self, n: int = 5):
        super().__init__("ngram")
        self.n = n

    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on n-gram similarity.

        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Get the raw content or use tokens
        content_a = self._get_content_for_ngrams(parsed_a)
        content_b = self._get_content_for_ngrams(parsed_b)

        if not content_a and not content_b:
            return 1.0
        if not content_a or not content_b:
            return 0.0

        # Generate n-grams
        ngrams_a = self._get_ngrams(content_a, self.n)
        ngrams_b = self._get_ngrams(content_b, self.n)

        if not ngrams_a and not ngrams_b:
            return 1.0
        if not ngrams_a or not ngrams_b:
            return 0.0

        # Calculate Sørensen–Dice coefficient of n-gram sets
        set_a = set(ngrams_a)
        set_b = set(ngrams_b)

        intersection = len(set_a.intersection(set_b))
        total = len(set_a) + len(set_b)

        if total == 0:
            return 0.0

        return (2.0 * intersection) / total

    def _get_content_for_ngrams(self, parsed: Dict[str, Any]) -> str:
        """
        Extract content suitable for n-gram analysis.

        Args:
            parsed: Parsed code representation

        Returns:
            String content for n-gram generation
        """
        content = ""
        tokens = parsed.get("tokens", [])
        if tokens:
            content = " ".join(tokens)
        else:
            raw = parsed.get("raw", "")
            if raw:
                content = re.sub(r"\s+", " ", raw.strip())

        # Normalize numeric literals to NUM and strings to STR
        content = re.sub(r"\b\d+(\.\d+)?\b", "NUM", content)
        content = re.sub(r'["\'].*?["\']', "STR", content, flags=re.DOTALL)

        return content

    def _get_ngrams(self, text: str, n: int) -> List[str]:
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

        ngrams = []
        for i in range(len(text) - n + 1):
            ngrams.append(text[i : i + n])
        return ngrams


class TokenNgramSimilarity(BaseSimilarityAlgorithm):
    """
    Token n-gram similarity algorithm.

    Creates n-grams from token sequences rather than characters.
    """

    def __init__(self, n: int = 2):
        super().__init__("token_ngram")
        self.n = n

    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on token n-gram similarity.

        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation

        Returns:
            Similarity score between 0.0 and 1.0
        """
        tokens_a = parsed_a.get("tokens", [])
        tokens_b = parsed_b.get("tokens", [])

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        # Generate token n-grams
        ngrams_a = self._get_token_ngrams(tokens_a, self.n)
        ngrams_b = self._get_token_ngrams(tokens_b, self.n)

        if not ngrams_a and not ngrams_b:
            return 1.0
        if not ngrams_a or not ngrams_b:
            return 0.0

        # Calculate Sørensen–Dice coefficient of token n-gram sets
        set_a = set(tuple(g) for g in ngrams_a)
        set_b = set(tuple(g) for g in ngrams_b)

        intersection = len(set_a.intersection(set_b))
        total = len(set_a) + len(set_b)

        if total == 0:
            return 0.0

        return (2.0 * intersection) / total

    def _get_token_ngrams(self, tokens: List[str], n: int) -> List[List[str]]:
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

        ngrams = []
        for i in range(len(tokens) - n + 1):
            ngrams.append(tokens[i : i + n])
        return ngrams
