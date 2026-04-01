"""
Scala code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class ScalaParser(BaseParser):
    """
    Scala code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'scala'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            functions = self._extract_functions(content)
            classes = self._extract_classes(content)
            traits = self._extract_traits(content)
            objects = self._extract_objects(content)
            imports = self._extract_imports(content)
            
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
                    'traits': traits,
                    'objects': objects,
                    'imports': imports
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
        patterns = [
            r'def\s+(\w+)',
            r'val\s+(\w+)\s*=',
        ]
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            functions.extend(matches)
        return list(set(functions))
    
    def _extract_classes(self, content: str) -> List[str]:
        pattern = r'class\s+(\w+)'
        return re.findall(pattern, content)
    
    def _extract_traits(self, content: str) -> List[str]:
        pattern = r'trait\s+(\w+)'
        return re.findall(pattern, content)
    
    def _extract_objects(self, content: str) -> List[str]:
        pattern = r'object\s+(\w+)'
        return re.findall(pattern, content)
    
    def _extract_imports(self, content: str) -> List[str]:
        pattern = r'import\s+([\w.]+)'
        return re.findall(pattern, content)


from .base_parser import ParserFactory
ParserFactory.register_parser('scala', ScalaParser)
ParserFactory.register_parser('sc', ScalaParser)
