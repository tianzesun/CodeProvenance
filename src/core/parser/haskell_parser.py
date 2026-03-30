"""
Haskell code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class HaskellParser(BaseParser):
    """
    Haskell code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'haskell'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Haskell file and return a representation suitable for similarity detection.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        try:
            # Extract tokens using basic tokenization
            tokens = self._tokenize_basic(content)
            
            # Extract function definitions
            functions = self._extract_functions(content)
            
            # Extract data types
            data_types = self._extract_data_types(content)
            
            # Extract type signatures
            type_sigs = self._extract_type_signatures(content)
            
            # Extract imports
            imports = self._extract_imports(content)
            
            # Extract class instances
            instances = self._extract_instances(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,  # Simplified - AST parsing requires tree-sitter
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'functions': functions,
                    'data_types': data_types,
                    'type_signatures': type_sigs,
                    'imports': imports,
                    'instances': instances
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
    
    def _extract_functions(self, content: str) -> List[str]:
        """
        Extract function definitions from Haskell code.
        
        Args:
            content: File content
            
        Returns:
            List of function names
        """
        # Match: functionName pattern = expression
        # Look for identifiers followed by = (but not in comments or strings)
        pattern = r'^(\w+)\s+[^=]+\s*=\s*.+$'
        matches = re.findall(pattern, content, re.MULTILINE)
        
        # Also match single-argument functions: func x = ...
        pattern2 = r'^(\w+)\s+=\s*.+$'
        matches2 = re.findall(pattern2, content, re.MULTILINE)
        
        return list(set(matches + matches2))
    
    def _extract_data_types(self, content: str) -> List[str]:
        """
        Extract data type declarations from Haskell code.
        
        Args:
            content: File content
            
        Returns:
            List of data type names
        """
        # Match: data TypeName or newtype TypeName or type TypeName
        patterns = [
            r'data\s+(\w+)',
            r'newtype\s+(\w+)',
            r'type\s+(\w+)',
        ]
        
        data_types = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            data_types.extend(matches)
        
        return data_types
    
    def _extract_type_signatures(self, content: str) -> List[str]:
        """
        Extract type signature declarations from Haskell code.
        
        Args:
            content: File content
            
        Returns:
            List of function names with signatures
        """
        # Match: functionName :: Type
        pattern = r'(\w+)\s*::'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_imports(self, content: str) -> List[str]:
        """
        Extract import statements from Haskell code.
        
        Args:
            content: File content
            
        Returns:
            List of imported modules
        """
        # Match: import ModuleName
        pattern = r'import\s+(?:qualified\s+)?(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_instances(self, content: str) -> List[str]:
        """
        Extract instance declarations from Haskell code.
        
        Args:
            content: File content
            
        Returns:
            List of instance declarations
        """
        # Match: instance ClassName Type
        pattern = r'instance\s+(\w+)\s+(\w+)'
        matches = re.findall(pattern, content)
        # Return as formatted strings
        return [f"{c} {t}" for c, t in matches]


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('haskell', HaskellParser)
ParserFactory.register_parser('hs', HaskellParser)
