"""
CodeProvenance Engine v1.

Basic token-based similarity using Jaccard similarity and n-gram overlap.
This is the foundational version with simple, fast comparison.
"""

from typing import Dict, Any, List, Set
from .base import BaseCodeProvenanceEngine
from .registry import register_engine


@register_engine("codeprovenance:v1")
class CodeProvenanceV1(BaseCodeProvenanceEngine):
    """Version 1: Basic token similarity.
    
    Features:
    - Jaccard similarity of token sets
    - N-gram overlap (configurable size)
    - Fast execution
    - Minimal dependencies
    
    Use cases:
    - Quick screening of large codebases
    - Baseline comparison
    - Real-time similarity checks
    """
    
    def __init__(self, ngram_size: int = 3):
        """Initialize v1 engine.
        
        Args:
            ngram_size: Size of n-grams for comparison (default: 3)
        """
        self._ngram_size = ngram_size
    
    @property
    def version(self) -> str:
        """Engine version identifier."""
        return "codeprovenance:v1"
    
    @property
    def name(self) -> str:
        """Human-readable engine name."""
        return "CodeProvenance v1 (Basic Token)"
    
    @property
    def description(self) -> str:
        """Engine description."""
        return "Basic token similarity using Jaccard and n-gram overlap"
    
    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        """Compare two code snippets.
        
        Args:
            code_a: First code snippet
            code_b: Second code snippet
            **kwargs: Additional parameters (ignored in v1)
            
        Returns:
            Similarity score in [0.0, 1.0]
        """
        # Tokenize both code snippets
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)
        
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        
        # Calculate Jaccard similarity
        jaccard_score = self._jaccard_similarity(tokens_a, tokens_b)
        
        # Calculate n-gram similarity
        ngram_score = self._ngram_similarity(tokens_a, tokens_b)
        
        # Weighted combination
        return 0.6 * jaccard_score + 0.4 * ngram_score
    
    def _tokenize(self, code: str) -> List[str]:
        """Tokenize source code.
        
        Simple tokenization: split on whitespace and punctuation.
        """
        import re
        
        # Remove comments
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        
        # Remove strings
        code = re.sub(r'["\'].*?["\']', 'STR', code, flags=re.DOTALL)
        
        # Tokenize
        tokens = re.findall(
            r'[a-zA-Z_]\w*|[0-9]+|[+\-*/%=<>&|^~!?:;,.()\[\]{}]',
            code
        )
        
        return [t for t in tokens if t]
    
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
        if len(tokens_a) < self._ngram_size or len(tokens_b) < self._ngram_size:
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
        for i in range(len(tokens) - self._ngram_size + 1):
            ngram = " ".join(tokens[i:i + self._ngram_size])
            ngrams.add(ngram)
        return ngrams
    
    def get_config(self) -> Dict[str, Any]:
        """Get engine configuration."""
        config = super().get_config()
        config.update({
            "ngram_size": self._ngram_size,
            "algorithm": "jaccard + ngram",
            "weights": {"jaccard": 0.6, "ngram": 0.4},
        })
        return config