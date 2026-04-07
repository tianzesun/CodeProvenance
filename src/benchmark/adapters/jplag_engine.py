"""Adapter implementing JPlag-like similarity for benchmark testing.

JPlag uses Greedy String Tiling (GST) - a token-based algorithm that
finds matching token sequences between two code fragments.

Reference: M. Wise, "Running JPlag with Object-Oriented Languages", 1996.

This implementation captures the essence of JPlag's approach:
1. Tokenize code (whitespace-normalized, case-insensitive)
2. Find maximal matching token sequences (tiles)
3. Compute overlap ratio as similarity score
"""
from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from src.benchmark.similarity.base_engine import BaseSimilarityEngine


class JPlagEngine(BaseSimilarityEngine):
    """JPlag-like similarity using Greedy String Tiling.
    
    Mimics JPlag's approach for benchmark comparison.
    """
    
    # Python keywords to include as tokens (JPlag treats them as structural)
    KEYWORDS = {
        'def', 'class', 'return', 'if', 'else', 'elif', 'for', 'while',
        'import', 'from', 'try', 'except', 'finally', 'with', 'as',
        'in', 'not', 'and', 'or', 'is', 'None', 'True', 'False',
        'pass', 'break', 'continue', 'raise', 'yield', 'lambda',
        'public', 'private', 'protected', 'static', 'void', 'int',
        'float', 'double', 'char', 'boolean', 'string',
        'new', 'this', 'super', 'extends', 'implements',
        'const', 'let', 'var', 'function', 'async', 'await',
        'do', 'switch', 'case', 'default', 'throw', 'catch',
        'interface', 'abstract', 'final', 'native', 'transient',
        'volatile', 'synchronized', 'typedef', 'struct', 'enum',
    }
    
    def __init__(self, min_match: int = 6):
        """Initialize JPlag-like engine.
        
        Args:
            min_match: Minimum tile length (JPlag default: 6).
        """
        self._min_match = min_match
    
    @property
    def name(self) -> str:
        return "jplag"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using GST-like approach.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Similarity score in [0.0, 1.0].
        """
        if not code_a or not code_b:
            return 0.0
        
        # Tokenize (JPlag-style: normalize whitespace, keep keywords,
        # treat identifiers as tokens)
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)
        
        if not tokens_a or not tokens_b:
            return 0.0
        
        # Compute max possible matches
        min_len = min(len(tokens_a), len(tokens_b))
        if min_len == 0:
            return 0.0
        
        # Greedy string tiling
        matched_a: Set[int] = set()
        matched_b: Set[int] = set()
        total_matched = 0
        
        tiles = self._find_all_tiles(tokens_a, tokens_b, matched_a, matched_b)
        
        for start_a, start_b, length in tiles:
            for i in range(length):
                matched_a.add(start_a + i)
                matched_b.add(start_b + i)
            total_matched += length
        
        # JPlag-style similarity: overlap / total tokens
        # Using average of both directions (like JPlag does)
        overlap_a = total_matched / len(tokens_a) if tokens_a else 0.0
        overlap_b = total_matched / len(tokens_b) if tokens_b else 0.0
        
        # Use minimum overlap (JPlag's default behavior)
        return max(0.0, min(1.0, min(overlap_a, overlap_b)))
    
    def _tokenize(self, code: str) -> List[str]:
        """Tokenize code JPlag-style.
        
        Preserves keywords and operators as structural tokens.
        Normalizes variable names to a placeholder.
        
        Args:
            code: Raw code string.
            
        Returns:
            List of normalized tokens.
        """
        # Normalize whitespace
        code = re.sub(r'\s+', ' ', code.strip())
        
        # Remove comments
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        
        # Extract tokens
        tokens = []
        i = 0
        while i < len(code):
            c = code[i]
            
            if c.isspace():
                i += 1
                continue
            
            # Keywords and identifiers
            if c.isalpha() or c == '_':
                j = i
                while j < len(code) and (code[j].isalnum() or code[j] == '_'):
                    j += 1
                word = code[i:j]
                
                if word in self.KEYWORDS:
                    # Keep keywords
                    tokens.append(word.lower())
                else:
                    # Normalize identifiers to placeholder
                    # This makes JPlag robust to renaming (Type-2 clones)
                    tokens.append('ID')
                
                i = j
                continue
            
            # String literals
            if c in ('"', "'"):
                tokens.append('STRING')
                i += 1
                while i < len(code) and code[i] != c:
                    if code[i] == '\\':
                        i += 1
                    i += 1
                i += 1
                continue
            
            # Numbers
            if c.isdigit():
                j = i
                while j < len(code) and (code[j].isdigit() or code[j] in '.eExXaAbBcCdDfF+-'):
                    j += 1
                tokens.append('NUM')
                i = j
                continue
            
            # Operators and punctuation (structural tokens)
            if c in '(){}[];,.:=+-*/%<>!&|^~@#?':
                tokens.append(c)
                i += 1
                continue
            
            # Skip other characters
            i += 1
        
        return tokens
    
    def _find_all_tiles(
        self,
        tokens_a: List[str],
        tokens_b: List[str],
        matched_a: Set[int],
        matched_b: Set[int],
    ) -> List[Tuple[int, int, int]]:
        """Find all maximal matching tiles using greedy approach.
        
        Args:
            tokens_a: Tokens from code A.
            tokens_b: Tokens from code B.
            matched_a: Already matched positions in A.
            matched_b: Already matched positions in B.
            
        Returns:
            List of (start_a, start_b, length) tuples.
        """
        tiles = []
        n = len(tokens_a)
        m = len(tokens_b)
        
        # Build suffix match index for efficiency
        # For each position pair, find max matching length
        match_len: Dict[Tuple[int, int], int] = {}
        
        for i in range(n - 1, -1, -1):
            if i in matched_a:
                continue
            for j in range(m - 1, -1, -1):
                if j in matched_b:
                    continue
                if tokens_a[i] == tokens_b[j]:
                    match_len[(i, j)] = match_len.get((i + 1, j + 1), 0) + 1
                else:
                    match_len[(i, j)] = 0
        
        # Find all maximal tiles above min_match length
        min_match = self._min_match
        checked_a: Set[int] = set()
        checked_b: Set[int] = set()
        
        while True:
            best_start_a = -1
            best_start_b = -1
            best_length = 0
            
            # Find longest unmatched tile
            for i in range(n - min_match + 1):
                if i in matched_a or i in checked_a:
                    continue
                for j in range(m - min_match + 1):
                    if j in matched_b or j in checked_b:
                        continue
                    length = match_len.get((i, j), 0)
                    if length > best_length:
                        best_length = length
                        best_start_a = i
                        best_start_b = j
            
            if best_length >= min_match:
                tiles.append((best_start_a, best_start_b, best_length))
                for k in range(best_length):
                    matched_a.add(best_start_a + k)
                    matched_b.add(best_start_b + k)
            else:
                break
        
        return tiles