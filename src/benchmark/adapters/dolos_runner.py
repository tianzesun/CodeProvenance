"""Dolos benchmark adapter.

Dolos is a source code plagiarism detection tool using winnowing-based
token comparison. Since npm install failed (tree-sitter build error),
this adapter implements the Dolos algorithm (winnowing + token fingerprinting)
to provide comparable benchmark results.

Reference: https://dolos.ugent.be/

The algorithm uses:
1. Token-based winnowing (similar to MOSS/YAP)
2. N-gram fingerprinting
3. Jaccard similarity for comparison
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Set, Tuple

from benchmark.similarity.base_engine import BaseSimilarityEngine


class DolosBenchmarkEngine(BaseSimilarityEngine):
    """Dolos-like similarity using winnowing algorithm.
    
    Implements the core Dolos algorithm:
    - Normalize code to tokens
    - Generate k-grams
    - Winnowing to select fingerprints
    - Jaccard similarity for comparison
    """
    
    # Winnowing parameters
    KGRAM_SIZE = 5      # Size of k-grams
    WINDOW_SIZE = 8     # Window size for winnowing
    
    def __init__(self, kgram_size: int = 5, window_size: int = 8):
        self._kgram_size = kgram_size
        self._window_size = window_size
    
    @property
    def name(self) -> str:
        return "dolos"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using winnowing algorithm."""
        if not code_a or not code_b:
            return 0.0
        
        # Tokenize
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)
        
        if not tokens_a or not tokens_b:
            return 0.0
        
        # Generate fingerprints with winnowing
        fp_a = self._winnow(tokens_a)
        fp_b = self._winnow(tokens_b)
        
        if not fp_a or not fp_b:
            return 0.0
        
        # Jaccard similarity
        intersection = len(fp_a & fp_b)
        union = len(fp_a | fp_b)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _tokenize(self, code: str) -> List[str]:
        """Normalize code to tokens (Dolos-style).
        
        Removes whitespace, comments, normalizes case,
        keeps keywords and operators.
        """
        import re
        
        # Remove comments
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        
        # Normalize whitespace and case
        code = code.lower().strip()
        
        # Tokenize: split on whitespace, punctuation
        tokens = re.findall(r'[a-zA-Z_]\w*|[0-9]+|[^\s\w]', code)
        
        # Filter out empty tokens
        return [t for t in tokens if t.strip()]
    
    def _kgrams(self, tokens: List[str]) -> List[Tuple[str, ...]]:
        """Generate k-grams from token list."""
        if len(tokens) < self._kgram_size:
            return [tuple(tokens)]
        
        return [tuple(tokens[i:i + self._kgram_size]) 
                for i in range(len(tokens) - self._kgram_size + 1)]
    
    def _winnow(self, tokens: List[str]) -> Set[int]:
        """Apply winnowing to generate fingerprints."""
        kgrams = self._kgrams(tokens)
        if not kgrams:
            return set()
        
        # Hash each k-gram
        hashes = []
        for kg in kgrams:
            h = hashlib.md5(str(kg).encode()).hexdigest()
            hashes.append(int(h[:12], 16))  # First 12 hex chars as hash
        
        # Apply winnowing
        fingerprints = set()
        window = self._window_size
        
        if len(hashes) <= window:
            fingerprints.add(min(hashes))
            return fingerprints
        
        for i in range(len(hashes) - window + 1):
            window_hashes = hashes[i:i + window]
            min_hash = min(window_hashes)
            fingerprints.add(min_hash)
        
        return fingerprints