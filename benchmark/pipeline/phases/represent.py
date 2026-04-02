"""Phase 3: IR Generation.

Generates intermediate representations from normalized code:
- AST-based representation
- Token-based representation
- Graph-based representation

Input: List[NormalizedCode]
Output: List[IntermediateRepresentation]

Usage:
    from benchmark.pipeline.phases.represent import RepresentationPhase

    phase = RepresentationPhase()
    representations = phase.execute(normalized_codes, config)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import ast
import re


@dataclass
class IntermediateRepresentation:
    """Intermediate representation of code.
    
    Attributes:
        code_id: Unique identifier for the code.
        normalized_content: Normalized code content.
        language: Programming language.
        ast_tree: AST representation (if available).
        tokens: Token list.
        representation_type: Type of representation (ast, token, graph).
        metadata: Additional metadata.
    """
    code_id: str
    normalized_content: str
    language: str
    ast_tree: Any = None
    tokens: List[str] = field(default_factory=list)
    representation_type: str = "token"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        """Check if representation is valid."""
        return bool(self.tokens) or self.ast_tree is not None


class RepresentationPhase:
    """Phase 3: IR Generation.
    
    This phase is responsible for:
    - Parsing normalized code into AST
    - Extracting tokens
    - Building graph representations
    
    Input: List[NormalizedCode] from normalization phase
    Output: List[IntermediateRepresentation] ready for comparison
    
    Usage:
        phase = RepresentationPhase()
        representations = phase.execute(normalized_codes, config)
    """
    
    def execute(
        self,
        normalized_codes: List[Any],
        config: Dict[str, Any],
    ) -> List[IntermediateRepresentation]:
        """Execute representation phase.
        
        Args:
            normalized_codes: List of NormalizedCode objects from normalization phase.
            config: Configuration for representation.
                - representation_type: Type of representation (ast, token, graph)
                - parse_ast: Whether to parse AST (default: True)
                - extract_tokens: Whether to extract tokens (default: True)
            
        Returns:
            List of IntermediateRepresentation objects.
        """
        representation_type = config.get('representation_type', 'token')
        parse_ast = config.get('parse_ast', True)
        extract_tokens = config.get('extract_tokens', True)
        
        results: List[IntermediateRepresentation] = []
        
        for i, normalized in enumerate(normalized_codes):
            # Get content from normalized code
            content = getattr(normalized, 'normalized_content', str(normalized))
            language = getattr(normalized, 'language', 'unknown')
            code_id = f"code_{i}"
            
            # Generate representation
            ast_tree = None
            tokens = []
            
            if parse_ast and language == 'python':
                ast_tree = self._parse_ast(content)
            
            if extract_tokens:
                tokens = self._extract_tokens(content, language)
            
            results.append(IntermediateRepresentation(
                code_id=code_id,
                normalized_content=content,
                language=language,
                ast_tree=ast_tree,
                tokens=tokens,
                representation_type=representation_type,
                metadata={'original_path': getattr(normalized, 'original_path', 'unknown')},
            ))
        
        return results
    
    def _parse_ast(self, code: str) -> Any:
        """Parse code into AST.
        
        Args:
            code: Normalized code string.
            
        Returns:
            AST tree or None if parsing fails.
        """
        try:
            return ast.parse(code)
        except SyntaxError:
            return None
    
    def _extract_tokens(self, code: str, language: str) -> List[str]:
        """Extract tokens from code.
        
        Args:
            code: Normalized code string.
            language: Programming language.
            
        Returns:
            List of tokens.
        """
        # Simple tokenization by splitting on whitespace and punctuation
        tokens = re.findall(r'\b\w+\b|[^\w\s]', code)
        return tokens
    
    def _build_graph(self, ast_tree: Any) -> Dict[str, Any]:
        """Build graph representation from AST.
        
        Args:
            ast_tree: AST tree.
            
        Returns:
            Graph representation dictionary.
        """
        if ast_tree is None:
            return {}
        
        graph = {
            'nodes': [],
            'edges': [],
        }
        
        # Walk AST and build graph
        for node in ast.walk(ast_tree):
            node_info = {
                'type': type(node).__name__,
                'lineno': getattr(node, 'lineno', 0),
                'col_offset': getattr(node, 'col_offset', 0),
            }
            graph['nodes'].append(node_info)
        
        return graph