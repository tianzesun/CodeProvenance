"""Identifier normalizer for rename-resilient plagiarism detection.

Normalizes all identifiers (variables, functions, classes) to canonical tokens
(ID_0, ID_1, ...) based on their first appearance order.

Example:
    Original:  def foo(x, y): return x + y
    Renamed:   def bar(a, b): return a + b
    Normalized:
       both -> def ID_0(ID_1, ID_2): return ID_1 + ID_2

This allows token-based similarity engines to detect Type-2 (rename) clones.

Usage:
    from src.backend.benchmark.normalization.identifier_normalizer import normalize_identifiers
    
    code_a = normalize_identifiers("def foo(x, y): return x + y")
    code_b = normalize_identifiers("def bar(a, b): return a + b")
    assert code_a == code_b  # Both normalized to same form
"""
from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


# Language keywords to NOT normalize
KEYWORDS: Set[str] = {
    # Python
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
    'while', 'with', 'yield',
    # Java
    'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch',
    'char', 'class', 'const', 'continue', 'default', 'do', 'double',
    'else', 'enum', 'extends', 'final', 'finally', 'float', 'for',
    'goto', 'if', 'implements', 'import', 'instanceof', 'int',
    'interface', 'long', 'native', 'new', 'package', 'private',
    'protected', 'public', 'return', 'short', 'static', 'strictfp',
    'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
    'transient', 'try', 'void', 'volatile', 'while',
    # JavaScript
    'var', 'let', 'const', 'function', 'return', 'if', 'else', 'for',
    'while', 'do', 'switch', 'case', 'break', 'continue', 'new', 'delete',
    'typeof', 'instanceof', 'void', 'in', 'of', 'async', 'await', 'yield',
    'class', 'extends', 'constructor', 'try', 'catch', 'finally', 'throw',
    'debugger', 'with', 'export', 'import',
    # Common built-ins
    'self', 'int', 'str', 'float', 'list', 'dict', 'set', 'tuple',
    'bool', 'object', 'string', 'array', 'Map', 'Set', 'List',
    'ArrayList', 'HashMap', 'Math', 'System', 'console', 'document',
    'print', 'input', 'range', 'len', 'sum', 'max', 'min',
    'Integer', 'String', 'Boolean', 'Double', 'Long', 'Float',
    'new', 'List', 'ArrayList',
}


def normalize_identifiers(code: str, language: str = "python") -> str:
    """Normalize all identifiers in code to canonical form.
    
    Replaces identifiers (x, foo, MyClass) with canonical tokens (ID_0, ID_1, ...)
    based on their first appearance order. Keywords and built-ins are preserved.
    
    Args:
        code: Source code string.
        language: Language identifier (python, java, javascript).
        
    Returns:
        Normalized code string with canonical identifiers.
        
    Example:
        >>> normalize_identifiers("def foo(x): return x + 1")
        'def ID_0(ID_1): return ID_1 + 1'
    """
    identifier_map: Dict[str, int] = {}
    counter = 0
    keywords = KEYWORDS
    
    def replace_ident(match: re.Match) -> str:
        nonlocal counter
        name = match.group(0)
        # Skip keywords, built-ins, and language-specific reserved words
        if name in keywords:
            return name
        # Canonicalize identifier
        if name not in identifier_map:
            # Assign next canonical ID
            identifier_map[name] = counter
            counter += 1
        return f"ID_{identifier_map[name]}"
    
    # Match identifiers (letters, underscores, digits; not starting with digit)
    result = re.sub(r'\b[a-zA-Z_]\w*\b', replace_ident, code)
    return result


class IdentifierNormalizer:
    """Normalizes code identifiers for rename-resilient comparison.
    
    Usage:
        normalizer = IdentifierNormalizer()
        code_a = normalizer.normalize("def foo(x): return x + 1")
        code_b = normalizer.normalize("def bar(y): return y + 1")
        # code_a == code_b after normalization
    """
    
    def __init__(self, language: str = "python"):
        self._language = language
    
    def normalize(self, code: str) -> str:
        """Normalize all identifiers in code."""
        return normalize_identifiers(code, self._language)
    
    def normalize_pair(self, code_a: str, code_b: str) -> tuple:
        """Normalize two code strings independently."""
        norm_a = normalize_identifiers(code_a, self._language)
        norm_b = normalize_identifiers(code_b, self._language)
        return norm_a, norm_b


# =============================================================================
# Normalized similarity engine wrapper
# =============================================================================


class NormalizedEngine:
    """Wraps any similarity engine with identifier normalization.
    
    Usage:
        from src.backend.benchmark.similarity.engines import TokenWinnowingEngine
        from src.backend.benchmark.normalization.identifier_normalizer import NormalizedEngine
        
        base_engine = TokenWinnowingEngine()
        normalized = NormalizedEngine(base_engine)
        score = normalized.compare(
            "def foo(x): return x + 1",
            "def bar(y): return y + 1"
        )  # High score even with renamed variables
    """
    
    def __init__(self, engine: Any, language: str = "python"):
        """Initialize normalizer wrapper.
        
        Args:
            engine: Similarity engine instance with compare() method.
            language: Language for keyword filtering.
        """
        self._engine = engine
        self._normalizer = IdentifierNormalizer(language)
        self._language = language
    
    @property
    def name(self) -> str:
        """Return normalized engine name."""
        base_name = getattr(self._engine, 'name', str(type(self._engine).__name__))
        if callable(base_name):
            base_name = base_name()
        return f"{base_name}_normalized"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings with identifier normalization.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Similarity score in [0, 1].
        """
        norm_a, norm_b = self._normalizer.normalize_pair(code_a, code_b)
        return self._engine.compare(norm_a, norm_b)