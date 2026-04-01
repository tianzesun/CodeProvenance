"""
C++ code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class CppParser(BaseParser):
    """
    C++ code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'cpp'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a C++ file and return a representation suitable for similarity detection.
        
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
            
            # Extract includes
            includes = self._extract_includes(content)
            
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
                    'includes': includes
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
        Extract tokens from C++ code.
        
        Args:
            content: File content
            
        Returns:
            List of tokens
        """
        return self._tokenize_basic(content)
    
    def _extract_functions(self, content: str) -> List[str]:
        """
        Extract function declarations from C++ code.
        
        Args:
            content: File content
            
        Returns:
            List of function names
        """
        # Match: return_type name(...) or return_type namespace::name(...)
        pattern = r'(?:void|int|float|double|char|bool|string|auto|auto\s+\*)\s+((?:\w+::)*\w+)\s*\('
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_types(self, content: str) -> List[str]:
        """
        Extract type declarations from C++ code.
        
        Args:
            content: File content
            
        Returns:
            List of type names
        """
        # Match: class Name, struct Name, enum Name, typedef Name, using Name =
        patterns = [
            r'class\s+(\w+)',
            r'struct\s+(\w+)',
            r'enum\s+(\w+)',
            r'typedef\s+\w+\s+(\w+)',
            r'using\s+(\w+)\s*=',
        ]
        
        types = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            types.extend(matches)
        
        return types
    
    def _extract_includes(self, content: str) -> List[str]:
        """
        Extract include statements from C++ code.
        
        Args:
            content: File content
            
        Returns:
            List of include paths
        """
        # Match: #include <path> or #include "path"
        pattern = r'#include\s+(?:<([^>]+)>|"([^"]+)")'
        matches = re.findall(pattern, content)
        
        # Flatten and filter empty matches
        includes = []
        for m in matches:
            if m[0]:
                includes.append(f'<{m[0]}>')
            elif m[1]:
                includes.append(f'"{m[1]}"')
        
        return includes


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('cpp', CppParser)
ParserFactory.register_parser('c++', CppParser)
