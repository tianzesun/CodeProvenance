"""
Forth code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class ForthParser(BaseParser):
    """
    Forth code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'forth'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            words = self._extract_words(content)
            constants = self._extract_constants(content)
            variables = self._extract_variables(content)
            structures = self._extract_structures(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'words': words,
                    'constants': constants,
                    'variables': variables,
                    'structures': structures
                }
            }
        except Exception as e:
            return {
                'language': self.language,
                'tokens': [],
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {'has_syntax_error': True, 'error': str(e)}
            }
    
    def _extract_words(self, content: str) -> List[str]:
        # Forth words are defined with : name ... ;
        pattern = r':\s+(\S+)'
        return re.findall(pattern, content)
    
    def _extract_constants(self, content: str) -> List[str]:
        pattern = r'constant\s+(\S+)'
        return re.findall(pattern, content)
    
    def _extract_variables(self, content: str) -> List[str]:
        pattern = r'variable\s+(\S+)'
        return re.findall(pattern, content)
    
    def _extract_structures(self, content: str) -> List[str]:
        patterns = [
            r'structure:\s+(\S+)',
            r'begin-structure\s+(\S+)',
        ]
        structures = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            structures.extend(matches)
        return structures


from .base_parser import ParserFactory
ParserFactory.register_parser('forth', ForthParser)
ParserFactory.register_parser('4th', ForthParser)
