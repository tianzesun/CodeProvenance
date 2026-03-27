"""
Winnowing-based similarity algorithm.

Implements the winnowing algorithm for document fingerprinting, effective for detecting
similar code despite insertions, deletions, and rearrangements.
"""

from typing import List, Dict, Any
from .base_similarity import BaseSimilarityAlgorithm
import hashlib


class WinnowingSimilarity(BaseSimilarityAlgorithm):
    """
    Winnowing similarity algorithm that implements the winnowing algorithm for
    code fingerprinting.
    
    Effective for detecting plagiarism and code similarity despite modifications.
    """
    
    def __init__(self, k: int = 5, t: int = 4):
        """
        Initialize the winnowing similarity algorithm.
        
        Args:
            k: Length of k-grams to hash
            t: Window size for selecting minimum hash values
        """
        super().__init__("winnowing")
        self.k = k
        self.t = t
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on winnowing fingerprints.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Get tokens for fingerprinting
        tokens_a = parsed_a.get('tokens', [])
        tokens_b = parsed_b.get('tokens', [])
        
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        
        # Generate fingerprints
        fingerprint_a = self._get_winnowing_fingerprint(tokens_a)
        fingerprint_b = self._get_winnowing_fingerprint(tokens_b)
        
        if not fingerprint_a and not fingerprint_b:
            return 1.0
        if not fingerprint_a or not fingerprint_b:
            return 0.0
        
        # Calculate similarity based on common fingerprints
        return self._jaccard_similarity(fingerprint_a, fingerprint_b)
    
    def _get_winnowing_fingerprint(self, tokens: List[str]) -> List[str]:
        """
        Generate a winnowing fingerprint from a list of tokens.
        
        Args:
            tokens: List of tokens
            
        Returns:
            List of fingerprint hashes
        """
        if len(tokens) < self.k:
            # If we don't have enough tokens for a k-gram, hash the whole thing
            if tokens:
                return [self._hash_grams(' '.join(tokens))]
            return []
        
        # Generate k-grams
        k_grams = []
        for i in range(len(tokens) - self.k + 1):
            k_gram = tokens[i:i+self.k]
            k_grams.append(' '.join(k_gram))
        
        # Hash the k-grams
        hashes = [self._hash_grams(gram) for gram in k_grams]
        
        # Apply the winnowing algorithm
        fingerprints = []
        for i in range(len(hashes) - self.t + 1):
            window = hashes[i:i+self.t]
            min_hash = min(window)
            min_index = window.index(min_hash)
            
            # Only add the hash if it's the minimum in its window and
            # it's not already the last added fingerprint (to avoid duplicates)
            if not fingerprints or fingerprints[-1] != min_hash:
                # Check if this minimum is also the minimum in the previous window
                # to avoid adding the same hash multiple times
                is_new_min = True
                if i > 0:
                    prev_window = hashes[i-1:i-1+self.t]
                    if min(prev_window) == min_hash:
                        is_new_min = False
                
                if is_new_min:
                    fingerprints.append(min_hash)
        
        return fingerprints
    
    def _hash_grams(self, text: str) -> str:
        """
        Hash a string using SHA256 and return hex digest.
        
        Args:
            text: String to hash
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _jaccard_similarity(self, set_a: List[str], set_b: List[str]) -> float:
        """
        Calculate Jaccard similarity between two lists.
        
        Args:
            set_a: First list
            set_b: Second list
            
        Returns:
            Jaccard similarity coefficient
        """
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        
        set_a_set = set(set_a)
        set_b_set = set(set_b)
        
        intersection = len(set_a_set.intersection(set_b_set))
        union = len(set_a_set.union(set_b_set))
        
        if union == 0:
            return 0.0
            
        return intersection / union
