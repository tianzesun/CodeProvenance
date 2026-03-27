"""
Java code parser using javalang library.
"""

import hashlib
from typing import List, Dict, Any
try:
    import javalang
    JAVALLANG_AVAILABLE = True
except ImportError:
    JAVALLANG_AVAILABLE = False

from .base_parser import BaseParser


class JavaParser(BaseParser):
    """
    Java code parser that extracts AST nodes and tokens.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'java'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Java file and return AST representation.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        if not JAVALLANG_AVAILABLE:
            # Fallback if javalang is not installed
            return self._fallback_parse(content)
        
        try:
            # Parse the AST
            tree = javalang.parse.parse(content)
            
            # Extract tokens
            tokens = list(javalang.tokenizer.tokenize(content))
            token_values = [token.value for token in tokens]
            
            # Convert AST to serializable format
            ast_dict = self._ast_to_dict(tree)
            
            return {
                'language': self.language,
                'tokens': token_values,
                'ast': ast_dict,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'package': tree.package.name if tree.package else None,
                    'imports': [imp.path for imp in tree.imports] if tree.imports else [],
                    'types': [type_decl.name for type_decl in tree.types] if tree.types else []
                }
            }
        except Exception as e:
            # Return error information for parse errors
            return {
                'language': self.language,
                'tokens': [],
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': True,
                    'error': str(e)
                }
            }
    
    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        """
        Fallback parsing when javalang is not available.
        
        Args:
            content: File content
            
        Returns:
            Basic parsed representation
        """
        return {
            'language': self.language,
            'tokens': self._tokenize_basic(content),
            'ast': None,
            'lines': content.splitlines(),
            'hash': self._get_file_hash(content),
            'metadata': {
                'has_syntax_error': False,
                'note': 'Using fallback parser - install javalang for full support'
            }
        }
    
    def _tokenize_basic(self, content: str) -> List[str]:
        """
        Basic tokenization by splitting on whitespace and punctuation.
        
        Args:
            content: File content
            
        Returns:
            List of tokens
        """
        import re
        # Split on whitespace and common punctuation
        tokens = re.findall(r'\b\w+\b|[^\w\s]', content)
        return [token for token in tokens if token.strip()]
    
    def _ast_to_dict(self, node) -> Any:
        """
        Convert a javalang AST node to a dictionary representation.
        
        Args:
            node: AST node to convert
            
        Returns:
            Dictionary/list/primitive representation of the node
        """
        if hasattr(node, '__dict__'):
            # Handle javalang AST nodes
            result = {'_type': node.__class__.__name__}
            for attr, value in node.__dict__.items():
                if not attr.startswith('_'):
                    result[attr] = self._ast_to_dict(value)
            return result
        elif isinstance(node, list):
            # Handle lists of nodes
            return [self._ast_to_dict(item) for item in node]
        else:
            # Handle primitive values (str, int, float, None, etc.)
            return node


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('java', JavaParser)
