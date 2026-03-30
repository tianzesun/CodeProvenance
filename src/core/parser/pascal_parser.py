"""
Pascal code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class PascalParser(BaseParser):
    """
    Pascal code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'pascal'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            functions = self._extract_functions(content)
            procedures = self._extract_procedures(content)
            types = self._extract_types(content)
            classes = self._extract_classes(content)
            units = self._extract_units(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'functions': functions,
                    'procedures': procedures,
                    'types': types,
                    'classes': classes,
                    'units': units
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
    
    def _extract_functions(self, content: str) -> List[str]:
        pattern = r'function\s+(\w+)\s*\('
        return re.findall(pattern, content)
    
    def _extract_procedures(self, content: str) -> List[str]:
        pattern = r'procedure\s+(\w+)\s*\('
        return re.findall(pattern, content)
    
    def _extract_types(self, content: str) -> List[str]:
        pattern = r'type\s+(\w+)\s*='
        return re.findall(pattern, content)
    
    def _extract_classes(self, content: str) -> List[str]:
        pattern = r'(?:class|record)\s+(\w+)'
        return re.findall(pattern, content)
    
    def _extract_units(self, content: str) -> List[str]:
        pattern = r'unit\s+(\w+)'
        return re.findall(pattern, content)


from .base_parser import ParserFactory
ParserFactory.register_parser('pascal', PascalParser)
ParserFactory.register_parser('pp', PascalParser)
