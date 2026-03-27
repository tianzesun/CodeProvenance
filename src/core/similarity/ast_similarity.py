"""
AST (Abstract Syntax Tree) based similarity algorithm.

Compares code based on structural similarity of ASTs.
"""

from typing import List, Dict, Any
from .base_similarity import BaseSimilarityAlgorithm
import hashlib


class ASTSimilarity(BaseSimilarityAlgorithm):
    """
    AST similarity algorithm that compares code based on Abstract Syntax Tree structure.
    
    Effective for detecting structural similarities despite variable renaming, etc.
    """
    
    def __init__(self):
        super().__init__("ast")
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on AST similarity.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        ast_a = parsed_a.get('ast')
        ast_b = parsed_b.get('ast')
        
        # If either AST is missing or there was a syntax error, fall back to token similarity
        if ast_a is None or ast_b is None:
            # Fall back to token-based similarity
            return self._fallback_token_similarity(parsed_a, parsed_b)
        
        # Calculate tree edit distance or similar metric
        # For simplicity, we'll use a basic approach: compare serialized AST structures
        try:
            similarity = self._calculate_ast_similarity(ast_a, ast_b)
            return max(0.0, min(1.0, similarity))
        except Exception:
            # If AST comparison fails, fall back to token similarity
            return self._fallback_token_similarity(parsed_a, parsed_b)
    
    def _calculate_ast_similarity(self, ast_a: Dict[str, Any], ast_b: Dict[str, Any]) -> float:
        """
        Calculate similarity between two AST representations.
        
        Args:
            ast_a: First AST representation
            ast_b: Second AST representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Convert ASTs to canonical string representations
        str_a = self._ast_to_canonical_string(ast_a)
        str_b = self._ast_to_canonical_string(ast_b)
        
        if not str_a and not str_b:
            return 1.0
        if not str_a or not str_b:
            return 0.0
        
        # Use a simple similarity metric based on longest common subsequence
        return self._string_similarity(str_a, str_b)
    
    def _ast_to_canonical_string(self, ast_node: Dict[str, Any]) -> str:
        """
        Convert AST to a canonical string representation.
        
        Args:
            ast_node: AST node dictionary
            
        Returns:
            Canonical string representation
        """
        if isinstance(ast_node, dict):
            # Sort keys for consistent ordering
            items = sorted(ast_node.items())
            parts = []
            for key, value in items:
                if key == '_type':
                    parts.append(f"TYPE:{value}")
                else:
                    parts.append(f"{key}:{self._ast_to_canonical_string(value)}")
            return "{" + "|".join(parts) + "}"
        elif isinstance(ast_node, list):
            parts = [self._ast_to_canonical_string(item) for item in ast_node]
            return "[" + ",".join(parts) + "]"
        else:
            # Handle primitive values
            return str(ast_node)
    
    def _string_similarity(self, str_a: str, str_b: str) -> float:
        """
        Calculate similarity between two strings using a simple ratio.
        
        Args:
            str_a: First string
            str_b: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not str_a and not str_b:
            return 1.0
        if not str_a or not str_b:
            return 0.0
        
        # Simple approach: use Jaccard similarity of character n-grams
        # For better performance, we could use Levenshtein distance or other metrics
        ngrams_a = self._get_char_ngrams(str_a, 3)
        ngrams_b = self._get_char_ngrams(str_b, 3)
        
        if not ngrams_a and not ngrams_b:
            return 1.0
        if not ngrams_a or not ngrams_b:
            return 0.0
        
        set_a = set(ngrams_a)
        set_b = set(ngrams_b)
        
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        
        if union == 0:
            return 0.0
            
        return intersection / union
    
    def _get_char_ngrams(self, text: str, n: int) -> List[str]:
        """
        Generate character n-grams from text.
        
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
            ngrams.append(text[i:i+n])
        return ngrams
    
    def _fallback_token_similarity(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Fallback to token-based similarity when AST comparison is not possible.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Import here to avoid circular imports
        from .token_similarity import TokenSimilarity
        token_sim = TokenSimilarity()
        return token_sim.compare(parsed_a, parsed_b)


# Register the parser with the factory (this would be done in __init__.py)
# from .base_similarity import ParserFactory
# ParserFactory.register_parser('ast', ASTSimilarity)
