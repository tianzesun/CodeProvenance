"""
Scheme code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class SchemeParser(BaseParser):
    """
    Scheme code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'scheme'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            definitions = self._extract_definitions(content)
            functions = self._extract_functions(content)
            macros = self._extract_macros(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'definitions': definitions,
                    'functions': functions,
                    'macros': macros
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
    
    def _extract_definitions(self, content: str) -> List[str]:
        pattern = r'\(define\s+(\w+)'
        return re.findall(pattern, content)
    
    def _extract_functions(self, content: str) -> List[str]:
        patterns = [
            r'\(define\s+\((\w+)',
            r'\(([\w-]+)\s+',
        ]
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            functions.extend(matches)
        return list(set(functions))
    
    def _extract_macros(self, content: str) -> List[str]:
        pattern = r'\(define-syntax\s+(\w+)'
        return re.findall(pattern, content)


from .base_parser import ParserFactory
ParserFactory.register_parser('scheme', SchemeParser)
ParserFactory.register_parser('scm', SchemeParser)
