"""Plugin: Longest Common Subsequence similarity engine.

Computes similarity based on normalized LCS length.
Good for detecting code that shares structural patterns.

Auto-registered as: lcs
"""
from benchmark.similarity.base_engine import BaseSimilarityEngine


class LCSEngine(BaseSimilarityEngine):
    """Longest Common Subsequence similarity engine."""

    def name(self) -> str:
        return "lcs"

    def description(self) -> str:
        return "Normalized Longest Common Subsequence similarity"

    def compare(self, code1: str, code2: str) -> float:
        """Compute normalized LCS similarity."""
        if not code1 and not code2:
            return 1.0
        if not code1 or not code2:
            return 0.0

        # Tokenize by whitespace for better results
        tokens1 = code1.split()
        tokens2 = code2.split()
        len1, len2 = len(tokens1), len(tokens2)
        max_len = max(len1, len2)

        # Space-optimized LCS
        prev = [0] * (len2 + 1)
        curr = [0] * (len2 + 1)

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if tokens1[i - 1] == tokens2[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(prev[j], curr[j - 1])
            prev, curr = curr, prev

        lcs_len = prev[len2]
        return lcs_len / max_len if max_len > 0 else 0.0
