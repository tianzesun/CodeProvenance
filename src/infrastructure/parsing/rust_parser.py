"""
Rust code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class RustParser(BaseParser):
    """
    Rust code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'rust'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Rust file and return a representation suitable for similarity detection.
        
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
            
            # Extract use statements (imports)
            uses = self._extract_uses(content)
            
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
                    'uses': uses
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
        Extract tokens from Rust code.
        
        Args:
            content: File content
            
        Returns:
            List of tokens
        """
        return self._tokenize_basic(content)
    
    def _extract_functions(self, content: str) -> List[str]:
        """
        Extract function declarations from Rust code.
        
        Args:
            content: File content
            
        Returns:
            List of function names
        """
        # Match: fn name(...) or async fn name(...)
        pattern = r'(?:async\s+)?fn\s+(\w+)\s*\('
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_types(self, content: str) -> List[str]:
        """
        Extract type declarations from Rust code.
        
        Args:
            content: File content
            
        Returns:
            List of type names
        """
        # Match: struct Name, enum Name, trait Name, type Name
        pattern = r'(?:struct|enum|trait|type)\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_uses(self, content: str) -> List[str]:
        """
        Extract use statements from Rust code.
        
        Args:
            content: File content
            
        Returns:
            List of use paths
        """
        # Match: use path::to::module
        pattern = r'use\s+([^;]+);'
        matches = re.findall(pattern, content)
        return [m.strip() for m in matches]


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('rust', RustParser)
