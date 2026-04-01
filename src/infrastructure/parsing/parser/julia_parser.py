"""
Julia code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class JuliaParser(BaseParser):
    """
    Julia code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'julia'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            tokens = self._tokenize_basic(content)
            functions = self._extract_functions(content)
            structs = self._extract_structs(content)
            macros = self._extract_macros(content)
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
                    'structs': structs,
                    'macros': macros,
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
            r'function\s+(\w+)',
            r'(\w+)\s*\([^)]*\)\s*=\s*.+',
            r'@inline\s+(\w+)',
        ]
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            functions.extend(matches)
        return list(set(functions))
    
    def _extract_structs(self, content: str) -> List[str]:
        patterns = [r'struct\s+(\w+)', r'mutable\s+struct\s+(\w+)']
        structs = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            structs.extend(matches)
        return structs
    
    def _extract_macros(self, content: str) -> List[str]:
        pattern = r'@(\w+)'
        return re.findall(pattern, content)
    
    def _extract_imports(self, content: str) -> List[str]:
        patterns = [
            r'using\s+([\w.:]+)',
            r'import\s+([\w.:]+)',
        ]
        imports = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            imports.extend(matches)
        return imports


from .base_parser import ParserFactory
ParserFactory.register_parser('julia', JuliaParser)
ParserFactory.register_parser('jl', JuliaParser)
