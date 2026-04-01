"""
Perl code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class PerlParser(BaseParser):
    """
    Perl code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'perl'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Perl file and return a representation suitable for similarity detection.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        try:
            # Extract tokens using basic tokenization
            tokens = self._tokenize_basic(content)
            
            # Extract subroutines
            subroutines = self._extract_subroutines(content)
            
            # Extract packages
            packages = self._extract_packages(content)
            
            # Extract uses/requires
            uses = self._extract_uses(content)
            
            # Extract my/our declarations
            variables = self._extract_variables(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,  # Simplified - AST parsing requires tree-sitter
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'subroutines': subroutines,
                    'packages': packages,
                    'uses': uses,
                    'variables': variables
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
    
    def _extract_subroutines(self, content: str) -> List[str]:
        """
        Extract subroutine definitions from Perl code.
        
        Args:
            content: File content
            
        Returns:
            List of subroutine names
        """
        # Match: sub subroutine_name
        pattern = r'sub\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_packages(self, content: str) -> List[str]:
        """
        Extract package declarations from Perl code.
        
        Args:
            content: File content
            
        Returns:
            List of package names
        """
        # Match: package PackageName;
        pattern = r'package\s+([\w:]+);'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_uses(self, content: str) -> List[str]:
        """
        Extract use/require statements from Perl code.
        
        Args:
            content: File content
            
        Returns:
            List of used modules
        """
        # Match: use ModuleName or require ModuleName
        patterns = [
            r'use\s+([\w:]+)',
            r'require\s+([\w:]+)',
        ]
        
        uses = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            uses.extend(matches)
        
        return uses
    
    def _extract_variables(self, content: str) -> List[str]:
        """
        Extract variable declarations from Perl code.
        
        Args:
            content: File content
            
        Returns:
            List of variable names
        """
        # Match: my $var_name or our $var_name
        pattern = r'(?:my|our)\s+\$([\w]+)'
        matches = re.findall(pattern, content)
        return matches


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('perl', PerlParser)
ParserFactory.register_parser('pl', PerlParser)
