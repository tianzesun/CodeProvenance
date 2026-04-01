"""
Arduino code parser using basic regex-based tokenization.
Arduino code is similar to C/C++ with setup() and loop() functions.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class ArduinoParser(BaseParser):
    """
    Arduino code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'arduino'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            functions = self._extract_functions(content)
            classes = self._extract_classes(content)
            includes = self._extract_includes(content)
            globals_ = self._extract_globals(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'functions': functions,
                    'classes': classes,
                    'includes': includes,
                    'global_variables': globals_
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
        # Arduino has setup() and loop() as special functions
        pattern = r'(?:void|int|bool|float|char)\s+(\w+)\s*\('
        return re.findall(pattern, content)
    
    def _extract_classes(self, content: str) -> List[str]:
        pattern = r'class\s+(\w+)'
        return re.findall(pattern, content)
    
    def _extract_includes(self, content: str) -> List[str]:
        pattern = r'#include\s+[<"]([^>"]+)[>"]'
        return re.findall(pattern, content)
    
    def _extract_globals(self, content: str) -> List[str]:
        pattern = r'(?:const\s+)?(?:int|bool|float|char|byte|void)\s+(\w+)\s*[;=]'
        return re.findall(pattern, content)


from .base_parser import ParserFactory
ParserFactory.register_parser('arduino', ArduinoParser)
