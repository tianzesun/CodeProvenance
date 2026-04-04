"""Example plugin: Jaccard similarity on character n-grams.

This is a simple demonstration engine that computes similarity
based on character 3-gram Jaccard index.

To use: the engine will be auto-registered as "jaccard_ngram".
"""
from benchmark.similarity.base_engine import BaseSimilarityEngine


class JaccardNGramEngine(BaseSimilarityEngine):
    """Character n-gram Jaccard similarity engine."""

    def name(self) -> str:
        return "jaccard_ngram"

    def description(self) -> str:
        return "Character 3-gram Jaccard similarity"

    def compare(self, code1: str, code2: str) -> float:
        """Compute Jaccard similarity of character 3-grams."""
        n = 3
        if len(code1) < n or len(code2) < n:
            return 0.0

        def ngrams(s):
            return set(s[i:i + n] for i in range(len(s) - n + 1))

        g1 = ngrams(code1)
        g2 = ngrams(code2)
        if not g1 and not g2:
            return 1.0
        if not g1 or not g2:
            return 0.0
        intersection = len(g1 & g2)
        union = len(g1 | g2)
        return intersection / union if union > 0 else 0.0
