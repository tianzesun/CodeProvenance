"""
Ruby code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class RubyParser(BaseParser):
    """
    Ruby code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'ruby'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Ruby file and return a representation suitable for similarity detection.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        try:
            # Extract tokens using basic tokenization
            tokens = self._tokenize_basic(content)
            
            # Extract method definitions
            methods = self._extract_methods(content)
            
            # Extract class definitions
            classes = self._extract_classes(content)
            
            # Extract module definitions
            modules = self._extract_modules(content)
            
            # Extract requires
            requires = self._extract_requires(content)
            
            # Extract includes/extends
            includes = self._extract_includes(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,  # Simplified - AST parsing requires tree-sitter
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'methods': methods,
                    'classes': classes,
                    'modules': modules,
                    'requires': requires,
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
    
    def _extract_methods(self, content: str) -> List[str]:
        """
        Extract method definitions from Ruby code.
        
        Args:
            content: File content
            
        Returns:
            List of method names
        """
        # Match: def method_name, def self.method_name, def ClassName.method_name
        patterns = [
            r'def\s+(?:self\.)?(\w+)',
            r'def\s+([A-Z]\w*(?:\.[a-z]\w*)?)',
        ]
        
        methods = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            methods.extend(matches)
        
        return methods
    
    def _extract_classes(self, content: str) -> List[str]:
        """
        Extract class definitions from Ruby code.
        
        Args:
            content: File content
            
        Returns:
            List of class names
        """
        # Match: class ClassName
        pattern = r'class\s+([A-Z]\w*)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_modules(self, content: str) -> List[str]:
        """
        Extract module definitions from Ruby code.
        
        Args:
            content: File content
            
        Returns:
            List of module names
        """
        # Match: module ModuleName
        pattern = r'module\s+([A-Z]\w*)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_requires(self, content: str) -> List[str]:
        """
        Extract require/require_relative statements from Ruby code.
        
        Args:
            content: File content
            
        Returns:
            List of required files
        """
        # Match: require '...' or require_relative '...'
        patterns = [
            r"require\s+['\"]([^'\"]+)['\"]",
            r"require_relative\s+['\"]([^'\"]+)['\"]",
        ]
        
        requires = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            requires.extend(matches)
        
        return requires
    
    def _extract_includes(self, content: str) -> List[str]:
        """
        Extract include/extend statements from Ruby code.
        
        Args:
            content: File content
            
        Returns:
            List of included modules
        """
        # Match: include ModuleName or extend ModuleName
        patterns = [
            r'include\s+([A-Z]\w*)',
            r'extend\s+([A-Z]\w*)',
        ]
        
        includes = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            includes.extend(matches)
        
        return includes


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('ruby', RubyParser)
