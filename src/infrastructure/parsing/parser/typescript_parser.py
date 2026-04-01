"""
TypeScript code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class TypeScriptParser(BaseParser):
    """
    TypeScript code parser that extracts tokens and metadata using regex patterns.
    TypeScript extends JavaScript with type annotations.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'typescript'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a TypeScript file and return a representation suitable for similarity detection.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        try:
            # Extract tokens using basic tokenization
            tokens = self._tokenize_basic(content)
            
            # Extract function declarations (with TypeScript syntax)
            functions = self._extract_functions(content)
            
            # Extract class declarations
            classes = self._extract_classes(content)
            
            # Extract interfaces
            interfaces = self._extract_interfaces(content)
            
            # Extract types
            types = self._extract_types(content)
            
            # Extract imports
            imports = self._extract_imports(content)
            
            # Extract exports
            exports = self._extract_exports(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,  # Simplified - AST parsing requires tree-sitter
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'functions': functions,
                    'classes': classes,
                    'interfaces': interfaces,
                    'types': types,
                    'imports': imports,
                    'exports': exports
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
        Extract function declarations from TypeScript code.
        
        Args:
            content: File content
            
        Returns:
            List of function names
        """
        # Match: function name(...): returnType, const name = ...: returnType, arrow functions
        patterns = [
            r'function\s+(\w+)\s*\(',
            r'(?:async\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*\w+)?\s*=>',
            r'(?:async\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function',
            r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{',
        ]
        
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            functions.extend(matches)
        
        return functions
    
    def _extract_classes(self, content: str) -> List[str]:
        """
        Extract class declarations from TypeScript code.
        
        Args:
            content: File content
            
        Returns:
            List of class names
        """
        # Match: class Name or class Name extends/implements
        pattern = r'class\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_interfaces(self, content: str) -> List[str]:
        """
        Extract interface declarations from TypeScript code.
        
        Args:
            content: File content
            
        Returns:
            List of interface names
        """
        # Match: interface Name
        pattern = r'interface\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_types(self, content: str) -> List[str]:
        """
        Extract type alias declarations from TypeScript code.
        
        Args:
            content: File content
            
        Returns:
            List of type names
        """
        # Match: type Name =
        pattern = r'type\s+(\w+)\s*='
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_imports(self, content: str) -> List[str]:
        """
        Extract import statements from TypeScript code.
        
        Args:
            content: File content
            
        Returns:
            List of import sources
        """
        # Match: import ... from '...' or import '...'
        patterns = [
            r"import\s+(?:\{[^}]+\}|[\w*]+)\s+from\s+['\"]([^'\"]+)['\"]",
            r"import\s+['\"]([^'\"]+)['\"]",
            r"import\s*=\s*require\s*\(['\"]([^'\"]+)['\"]",
        ]
        
        imports = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            imports.extend(matches)
        
        return imports
    
    def _extract_exports(self, content: str) -> List[str]:
        """
        Extract export statements from TypeScript code.
        
        Args:
            content: File content
            
        Returns:
            List of exported names
        """
        # Match: export ..., export default ..., export { ... }
        patterns = [
            r'export\s+default\s+(\w+)',
            r'export\s+(?:const|let|var|function|class|interface|type)\s+(\w+)',
        ]
        
        exports = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            exports.extend(matches)
        
        return exports


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('typescript', TypeScriptParser)
ParserFactory.register_parser('ts', TypeScriptParser)
