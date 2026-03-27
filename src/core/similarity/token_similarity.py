"""
Token-based similarity algorithm.

Compares code based on token sequences using Jaccard similarity or other token-based metrics.
"""

from typing import List, Dict, Any
from .base_similarity import BaseSimilarityAlgorithm
import re


class TokenSimilarity(BaseSimilarityAlgorithm):
    """
    Token similarity algorithm that compares code based on token sequences.
    
    Uses Jaccard similarity of token sets or sequence similarity algorithms.
    """
    
    def __init__(self):
        super().__init__("token")
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on token similarity.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        tokens_a = parsed_a.get('tokens', [])
        tokens_b = parsed_b.get('tokens', [])
        
        if not tokens_a and not tokens_b:
            return 1.0  # Both empty
        if not tokens_a or not tokens_b:
            return 0.0  # One empty
        
        # Use Jaccard similarity of token sets
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        
        if union == 0:
            return 0.0
            
        return intersection / union


class SequenceTokenSimilarity(BaseSimilarityAlgorithm):
    """
    Token similarity algorithm that considers token sequence order.
    
    Uses a simplified version of the Longest Common Subsequence (LCS) algorithm.
    """
    
    def __init__(self):
        super().__init__("sequence_token")
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on token sequence similarity.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        tokens_a = parsed_a.get('tokens', [])
        tokens_b = parsed_b.get('tokens', [])
        
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        
        # Use Longest Common Subsequence (LCS) similarity
        lcs_length = self._lcs_length(tokens_a, tokens_b)
        max_length = max(len(tokens_a), len(tokens_b))
        
        if max_length == 0:
            return 0.0
            
        return lcs_length / max_length
    
    def _lcs_length(self, seq1: List[str], seq2: List[str]) -> int:
        """
        Calculate the length of the Longest Common Subsequence.
        
        Args:
            seq1: First sequence
            seq2: Second sequence
            
        Returns:
            Length of LCS
        """
        m, n = len(seq1), len(seq2)
        # Create a 2D array to store lengths of longest common subsequence
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        # Build the dp array from bottom up
        for i in range(m + 1):
            for j in range(n + 1):
                if i == 0 or j == 0:
                    dp[i][j] = 0
                elif seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]
