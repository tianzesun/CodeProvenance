"""
Go code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class GoParser(BaseParser):
    """
    Go code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'go'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Go file and return a representation suitable for similarity detection.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        try:
            # Extract tokens using basic tokenization
            tokens = self._tokenize_basic(content)
            
            # Extract function declarations
            functions = self._extract_functions(content)
            
            # Extract type declarations
            types = self._extract_types(content)
            
            # Extract imports
            imports = self._extract_imports(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,  # Simplified - AST parsing requires tree-sitter
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'functions': functions,
                    'types': types,
                    'imports': imports
                }
            }
        except Exception as e:
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
    
    def _extract_tokens(self, content: str) -> List[str]:
        """
        Extract tokens from Go code.
        
        Args:
            content: File content
            
        Returns:
            List of tokens
        """
        return self._tokenize_basic(content)
    
    def _extract_functions(self, content: str) -> List[str]:
        """
        Extract function declarations from Go code.
        
        Args:
            content: File content
            
        Returns:
            List of function names
        """
        # Match: func name(...) or func (receiver) name(...)
        pattern = r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\('
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_types(self, content: str) -> List[str]:
        """
        Extract type declarations from Go code.
        
        Args:
            content: File content
            
        Returns:
            List of type names
        """
        # Match: type Name struct/interface/etc
        pattern = r'type\s+(\w+)\s+'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_imports(self, content: str) -> List[str]:
        """
        Extract import statements from Go code.
        
        Args:
            content: File content
            
        Returns:
            List of import paths
        """
        # Match: import "path" or import (
        pattern = r'import\s+(?:"([^"]+)")?'
        matches = re.findall(pattern, content)
        return [m for m in matches if m]


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('go', GoParser)
