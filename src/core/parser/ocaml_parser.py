"""
OCaml code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class OCamlParser(BaseParser):
    """
    OCaml code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'ocaml'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse an OCaml file and return a representation suitable for similarity detection.
        """
        try:
            tokens = self._tokenize_basic(content)
            functions = self._extract_functions(content)
            types = self._extract_types(content)
            modules = self._extract_modules(content)
            lets = self._extract_let_bindings(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'functions': functions,
                    'types': types,
                    'modules': modules,
                    'let_bindings': lets
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
        # Match: let rec function_name or let function_name
        patterns = [r'let\s+rec\s+(\w+)', r'let\s+(\w+)\s*\(']
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            functions.extend(matches)
        return functions
    
    def _extract_types(self, content: str) -> List[str]:
        pattern = r'type\s+(\w+)'
        return re.findall(pattern, content)
    
    def _extract_modules(self, content: str) -> List[str]:
        patterns = [r'module\s+(\w+)', r'open\s+(\w+)']
        modules = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            modules.extend(matches)
        return modules
    
    def _extract_let_bindings(self, content: str) -> List[str]:
        pattern = r'let\s+(?:rec\s+)?(\w+)'
        return re.findall(pattern, content)


from .base_parser import ParserFactory
ParserFactory.register_parser('ocaml', OCamlParser)
ParserFactory.register_parser('ml', OCamlParser)
