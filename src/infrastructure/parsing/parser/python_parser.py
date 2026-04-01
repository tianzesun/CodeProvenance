"""
Python-specific code parser using the built-in ast module.
"""

import ast
import hashlib
from typing import List, Dict, Any
from .base_parser import BaseParser


class PythonParser(BaseParser):
    """
    Python code parser that extracts AST nodes and tokens.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'python'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Python file and return AST representation.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        try:
            # Parse the AST
            tree = ast.parse(content)
            
            # Extract tokens (simplified - in practice you'd use tokenize module)
            tokens = self._extract_tokens(content)
            
            # Convert AST to serializable format
            ast_dict = self._ast_to_dict(tree)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': ast_dict,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'node_count': len(list(ast.walk(tree))),
                    'has_syntax_error': False
                }
            }
        except SyntaxError as e:
            # Return error information for syntax errors
            return {
                'language': self.language,
                'tokens': [],
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': True,
                    'error': str(e),
                    'error_line': e.lineno,
                    'error_offset': e.offset
                }
            }
    
    def _extract_tokens(self, content: str) -> List[str]:
        """
        Extract tokens from Python code using the tokenize module.
        
        Args:
            content: File content
            
        Returns:
            List of tokens
        """
        import io
        import tokenize
        
        tokens = []
        try:
            # Use io.StringIO to create a file-like object from the string
            file_obj = io.StringIO(content)
            
            # Tokenize the content
            for token in tokenize.generate_tokens(file_obj.readline):
                # Skip certain token types if desired
                if token.type not in (tokenize.ENCODING, tokenize.NEWLINE, tokenize.NL):
                    tokens.append(token.string)
        except Exception:
            # Fallback to basic tokenization if tokenize fails
            tokens = self._tokenize_basic(content)
        
        return tokens
    
    def _tokenize_basic(self, content: str) -> List[str]:
        """
        Basic tokenization by splitting on whitespace and punctuation.
        This is a fallback for languages without specific tokenizers.
        
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
        Convert an AST node to a dictionary representation.
        
        Args:
            node: AST node to convert
            
        Returns:
            Dictionary/list/primitive representation of the node
        """
        if isinstance(node, ast.AST):
            # Recursively convert AST nodes
            result = {'_type': node.__class__.__name__}
            for field, value in ast.iter_fields(node):
                result[field] = self._ast_to_dict(value)
            return result
        elif isinstance(node, list):
            # Handle lists of nodes
            return [self._ast_to_dict(item) for item in node]
        else:
            # Handle primitive values (str, int, float, None, etc.)
            return node


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('python', PythonParser)
