"""
Blaise code parser using basic regex-based tokenization.
Blaise is a Pascal-like language used in healthcare applications.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class BlaiseParser(BaseParser):
    """
    Blaise code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'blaise'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            procedures = self._extract_procedures(content)
            functions = self._extract_functions(content)
            tables = self._extract_tables(content)
            fields = self._extract_fields(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'procedures': procedures,
                    'functions': functions,
                    'tables': tables,
                    'fields': fields
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
    
    def _extract_procedures(self, content: str) -> List[str]:
        pattern = r'procedure\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)
    
    def _extract_functions(self, content: str) -> List[str]:
        pattern = r'function\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)
    
    def _extract_tables(self, content: str) -> List[str]:
        pattern = r'table\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)
    
    def _extract_fields(self, content: str) -> List[str]:
        pattern = r'field\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)


from .base_parser import ParserFactory
ParserFactory.register_parser('blaise', BlaiseParser)
