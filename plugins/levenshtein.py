"""Plugin: Levenshtein distance similarity engine.

Computes normalized Levenshtein distance as a similarity score.
Good for detecting small edits and typos.

Auto-registered as: levenshtein
"""
from benchmark.similarity.base_engine import BaseSimilarityEngine


class LevenshteinEngine(BaseSimilarityEngine):
    """Normalized Levenshtein distance similarity engine."""

    def name(self) -> str:
        return "levenshtein"

    def description(self) -> str:
        return "Normalized Levenshtein distance similarity"

    def compare(self, code1: str, code2: str) -> float:
        """Compute normalized Levenshtein similarity."""
        if not code1 and not code2:
            return 1.0
        if not code1 or not code2:
            return 0.0

        len1, len2 = len(code1), len(code2)
        max_len = max(len1, len2)

        # Optimized: only keep two rows
        prev = list(range(len2 + 1))
        curr = [0] * (len2 + 1)

        for i in range(1, len1 + 1):
            curr[0] = i
            for j in range(1, len2 + 1):
                cost = 0 if code1[i - 1] == code2[j - 1] else 1
                curr[j] = min(
                    curr[j - 1] + 1,      # insertion
                    prev[j] + 1,           # deletion
                    prev[j - 1] + cost,    # substitution
                )
            prev, curr = curr, prev

        distance = prev[len2]
        return 1.0 - (distance / max_len) if max_len > 0 else 0.0
