"""
SQL code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class SQLParser(BaseParser):
    """
    SQL code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'sql'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            tables = self._extract_tables(content)
            views = self._extract_views(content)
            functions = self._extract_functions(content)
            procedures = self._extract_procedures(content)
            indexes = self._extract_indexes(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'tables': tables,
                    'views': views,
                    'functions': functions,
                    'procedures': procedures,
                    'indexes': indexes
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
    
    def _extract_tables(self, content: str) -> List[str]:
        patterns = [
            r'CREATE\s+TABLE\s+(\w+)',
            r'FROM\s+(\w+)',
        ]
        tables = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            tables.extend(matches)
        return list(set(tables))
    
    def _extract_views(self, content: str) -> List[str]:
        pattern = r'CREATE\s+VIEW\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)
    
    def _extract_functions(self, content: str) -> List[str]:
        pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)
    
    def _extract_procedures(self, content: str) -> List[str]:
        pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)
    
    def _extract_indexes(self, content: str) -> List[str]:
        pattern = r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)'
        return re.findall(pattern, content, re.IGNORECASE)


from .base_parser import ParserFactory
ParserFactory.register_parser('sql', SQLParser)
