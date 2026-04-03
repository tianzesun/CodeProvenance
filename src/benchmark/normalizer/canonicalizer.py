"""Canonicalization layer for code similarity detection.

This is the missing layer that fixes Type-2 (renamed) clone detection.

Current pipeline: code → token/AST → similarity (FAILS on renamed code)
Fixed pipeline:  code → canonical form → token/AST → similarity

Canonicalization handles:
1. Identifier normalization (rename → canonical tokens v1, v2, v3)
2. Literal abstraction (42 → LITERAL_INT)
3. Control-flow normalization (while/for → unified loop)
4. Whitespace/comment removal

Usage:
    from benchmark.normalization.canonicalizer import Canonicalizer
    
    canonicalizer = Canonicalizer()
    code_a_canon = canonicalizer.canonicalize(code_a)
    code_b_canon = canonicalizer.canonicalize(code_b)
    score = engine.compare(code_a_canon, code_b_canon)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CanonicalizationConfig:
    """Configuration for canonicalization pipeline."""
    normalize_identifiers: bool = True
    abstract_literals: bool = True
    normalize_control_flow: bool = False
    remove_comments: bool = True
    remove_whitespace: bool = True
    normalize_case: bool = False
    preserve_keywords: bool = True


@dataclass
class CanonicalizationResult:
    """Result of canonicalization."""
    original: str
    canonical: str
    identifier_map: Dict[str, str] = field(default_factory=dict)
    literal_map: Dict[str, str] = field(default_factory=dict)
    num_identifiers_normalized: int = 0
    num_literals_abstracted: int = 0


class Canonicalizer:
    """Code canonicalizer for similarity detection.
    
    Transforms code into a canonical form that is invariant to:
    - Variable/method renaming
    - Literal value changes
    - Comment differences
    - Whitespace differences
    
    This is the key layer that enables Type-2 clone detection.
    
    Usage:
        canonicalizer = Canonicalizer()
        canon_result = canonicalizer.canonicalize(code)
        print(canon_result.canonical)
        print(f"Normalized {canon_result.num_identifiers_normalized} identifiers")
    """
    
    # Programming language keywords to preserve
    PYTHON_KEYWORDS = {
        'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
        'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
        'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not',
        'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
        # Built-ins often used in patterns
        'True', 'False', 'None', 'self',
    }
    
    JAVA_KEYWORDS = {
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch',
        'char', 'class', 'const', 'continue', 'default', 'do', 'double',
        'else', 'enum', 'extends', 'final', 'finally', 'float', 'for',
        'goto', 'if', 'implements', 'import', 'instanceof', 'int',
        'interface', 'long', 'native', 'new', 'package', 'private',
        'protected', 'public', 'return', 'short', 'static', 'strictfp',
        'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
        'transient', 'try', 'void', 'volatile', 'while',
    }
    
    # Built-in functions to preserve
    COMMON_BUILTINS = {
        'len', 'range', 'int', 'float', 'str', 'list', 'dict', 'set',
        'tuple', 'bool', 'type', 'isinstance', 'issubclass', 'hasattr',
        'getattr', 'setattr', 'enumerate', 'zip', 'map', 'filter', 'sorted',
        'print', 'open', 'input', 'super', 'min', 'max', 'sum', 'abs',
        'round', 'len', 'append', 'extend', 'insert', 'remove', 'pop',
        'clear', 'index', 'count', 'sort', 'reverse', 'copy',
    }
    
    JAVA_COMMON = {
        'System', 'String', 'Integer', 'Double', 'Boolean', 'List',
        'ArrayList', 'HashMap', 'Map', 'Set', 'Iterator', 'Arrays',
        'Math', 'Class', 'Object', 'Exception', 'RuntimeException',
        'StringBuilder', 'Arrays', 'Collections', 'Optional', 'Stream',
    }
    
    def __init__(self, config: Optional[CanonicalizationConfig] = None):
        """Initialize canonicalizer.
        
        Args:
            config: Canonicalization configuration.
        """
        self.config = config or CanonicalizationConfig()
        self._keywords: Set[str] = set()
    
    def set_language(self, language: str) -> "Canonicalizer":
        """Set language for keyword recognition.
        
        Args:
            language: Language identifier ('python', 'java', etc.).
            
        Returns:
            Self for chaining.
        """
        if language == 'java':
            self._keywords = self.JAVA_KEYWORDS | self.JAVA_COMMON
        else:
            self._keywords = self.PYTHON_KEYWORDS | self.COMMON_BUILTINS
        return self
    
    def canonicalize(self, code: str) -> CanonicalizationResult:
        """Canonicalize source code.
        
        Args:
            code: Source code string.
            
        Returns:
            CanonicalizationResult with canonical code and metadata.
        """
        original = code
        result = CanonicalizationResult(
            original=code,
            canonical=code,
        )
        
        # Pipeline: ordered transformations
        processed = code
        
        # 1. Remove comments
        if self.config.remove_comments:
            processed = self._remove_comments(processed)
        
        # 2. Abstract literals
        if self.config.abstract_literals:
            processed, literals = self._abstract_literals(processed)
            result.literal_map = literals
            result.num_literals_abstracted = len(literals)
        
        # 3. Normalize identifiers
        if self.config.normalize_identifiers:
            processed, id_map = self._normalize_identifiers(processed)
            result.identifier_map = id_map
            result.num_identifiers_normalized = len(id_map)
        
        # 4. Normalize case (optional)
        if self.config.normalize_case:
            processed = processed.lower()
        
        # 5. Normalize control flow (optional)
        if self.config.normalize_control_flow:
            processed = self._normalize_control_flow(processed)
        
        # 6. Remove/normalize whitespace
        if self.config.remove_whitespace:
            processed = self._normalize_whitespace(processed)
        
        result.canonical = processed
        return result
    
    def _remove_comments(self, code: str) -> str:
        """Remove comments from code.
        
        Args:
            code: Source code.
            
        Returns:
            Code without comments.
        """
        # Remove Python/JS single-line comments
        code = re.sub(r'#.*?$', '', code, flags=re.MULTILINE)
        # Remove C-style single-line comments
        code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)
        # Remove multi-line comments (C, Java, JS, etc.)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        # Remove Python docstrings
        code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
        code = re.sub(r"'''.*?'''", '', code, flags=re.DOTALL)
        return code
    
    def _abstract_literals(self, code: str) -> Tuple[str, Dict[str, str]]:
        """Replace literal values with abstract tokens.
        
        Args:
            code: Source code.
            
        Returns:
            Tuple of (code with abstracted literals, literal map).
        """
        literal_map: Dict[str, str] = {}
        counter = 0
        
        # Integer literals (handle hex, octal, binary)
        def replace_int(match: re.Match) -> str:
            nonlocal counter
            val = match.group(0)
            if val not in literal_map:
                counter += 1
                literal_map[val] = "LIT_INT"
            return literal_map[val]
        
        code = re.sub(
            r'\b(0x[0-9a-fA-F]+|0o[0-7]+|0b[01]+|\d+)\b',
            replace_int,
            code
        )
        
        # Float literals
        def replace_float(match: re.Match) -> str:
            nonlocal counter
            val = match.group(0)
            if val not in literal_map:
                counter += 1
                literal_map[val] = "LIT_FLOAT"
            return literal_map[val]
        
        code = re.sub(
            r'\b\d+\.\d+([eE][+-]?\d+)?\b|\b0[xX][0-9a-fA-F]+\.?\d*[pP][+-]?\d+\b',
            replace_float,
            code
        )
        
        # String literals
        def replace_string(match: re.Match) -> str:
            val = match.group(0)
            if val not in literal_map:
                literal_map[val] = "LIT_STR"
            return literal_map[val]
        
        # Double-quoted strings
        code = re.sub(r'"(?:[^"\\]|\\.)*"', replace_string, code)
        # Single-quoted strings
        code = re.sub(r"'(?:[^'\\]|\\.)*'", replace_string, code)
        
        return code, literal_map
    
    def _normalize_identifiers(self, code: str) -> Tuple[str, Dict[str, str]]:
        """Replace identifiers with canonical names.
        
        Variables are renamed to v_1, v_2, etc. based on first occurrence order.
        Keywords and built-in functions are preserved.
        
        Args:
            code: Source code.
            
        Returns:
            Tuple of (code with normalized identifiers, identifier map).
        """
        # Extract all identifiers
        all_idents: List[str] = []
        for match in re.finditer(r'\b([a-zA-Z_]\w*)\b', code):
            ident = match.group(1)
            if ident not in self._keywords and ident not in all_idents:
                all_idents.append(ident)
        
        # Create mapping: first occurrence order -> canonical name
        ident_map: Dict[str, str] = {}
        for i, ident in enumerate(all_idents, 1):
            ident_map[ident] = f"v_{i}"
        
        # Replace in code (longer identifiers first to avoid partial matches)
        sorted_idents = sorted(ident_map.keys(), key=len, reverse=True)
        processed = code
        
        for ident in sorted_idents:
            processed = re.sub(
                r'\b' + re.escape(ident) + r'\b',
                ident_map[ident],
                processed
            )
        
        return processed, ident_map
    
    def _normalize_control_flow(self, code: str) -> str:
        """Normalize control flow constructs.
        
        Converts equivalent control structures to a common form.
        
        Args:
            code: Source code.
            
        Returns:
            Code with normalized control flow.
        """
        # Convert for-loop patterns to a canonical form
        # "for x in range(...)" -> "LOOP_BLOCK"
        code = re.sub(r'for\s+\w+\s+in\s+range\s*\(', 'LOOP_BLOCK range(', code)
        
        # Convert while to canonical form
        code = re.sub(r'while\s+\(?\s*True\s*\)?', 'WHILE_TRUE', code)
        
        return code
    
    def _normalize_whitespace(self, code: str) -> str:
        """Normalize whitespace in code.
        
        Args:
            code: Source code.
            
        Returns:
            Code with normalized whitespace.
        """
        # Remove leading/trailing whitespace per line
        lines = [line.strip() for line in code.split('\n')]
        # Remove empty lines
        lines = [line for line in lines if line]
        # Join with single space
        return ' '.join(lines)


class CanonicalComparePipeline:
    """Pipeline that applies canonicalization before similarity comparison.
    
    This wraps any engine to provide canonicalized comparison.
    
    Usage:
        from benchmark.similarity.engines import HybridEngine
        from benchmark.normalization.canonicalizer import CanonicalComparePipeline
        
        pipeline = CanonicalComparePipeline(HybridEngine())
        score = pipeline.compare(code_a, code_b)
    """
    
    def __init__(
        self,
        engine,  # Any engine with compare(code_a, code_b) -> float
        canonicalizer: Optional[Canonicalizer] = None,
    ):
        """Initialize pipeline.
        
        Args:
            engine: Similarity engine instance.
            canonicalizer: Canonicalizer instance.
        """
        self._engine = engine
        self._canonicalizer = canonicalizer or Canonicalizer()
    
    @property
    def name(self) -> str:
        """Return pipeline name."""
        return f"{self._engine.name}_canon"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code snippets with canonicalization.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Similarity score [0, 1].
        """
        canon_a = self._canonicalizer.canonicalize(code_a)
        canon_b = self._canonicalizer.canonicalize(code_b)
        return self._engine.compare(canon_a.canonical, canon_b.canonical)
    
    def compare_with_canonicals(
        self, code_a: str, code_b: str
    ) -> Tuple[float, CanonicalizationResult, CanonicalizationResult]:
        """Compare and return canonicalized code.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Tuple of (similarity score, canonical_a, canonical_b).
        """
        canon_a = self._canonicalizer.canonicalize(code_a)
        canon_b = self._canonicalizer.canonicalize(code_b)
        score = self._engine.compare(canon_a.canonical, canon_b.canonical)
        return score, canon_a, canon_b


def create_canonical_engines(engines: Dict[str, Any]) -> Dict[str, Any]:
    """Create canonicalized versions of engines.
    
    Args:
        engines: Dict of engine_name -> engine instance.
        
    Returns:
        Dict of engine_name -> engine/pipeline instance.
    """
    result = {}
    for name, engine in engines.items():
        result[name] = engine
        result[f"{name}_canonical"] = CanonicalComparePipeline(
            engine, Canonicalizer()
        )
    return result