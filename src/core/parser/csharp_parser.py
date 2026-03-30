"""
C# code parser using basic regex-based tokenization.
"""

from typing import List, Dict, Any
import re
from .base_parser import BaseParser


class CSharpParser(BaseParser):
    """
    C# code parser that extracts tokens and metadata using regex patterns.
    """
    
    def __init__(self):
        super().__init__()
        self.language = 'csharp'
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a C# file and return a representation suitable for similarity detection.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation
        """
        try:
            # Extract tokens using basic tokenization
            tokens = self._tokenize_basic(content)
            
            # Extract method declarations
            methods = self._extract_methods(content)
            
            # Extract class declarations
            classes = self._extract_classes(content)
            
            # Extract struct declarations
            structs = self._extract_structs(content)
            
            # Extract interface declarations
            interfaces = self._extract_interfaces(content)
            
            # Extract enum declarations
            enums = self._extract_enums(content)
            
            # Extract namespaces
            namespaces = self._extract_namespaces(content)
            
            # Extract using statements
            usings = self._extract_usings(content)
            
            return {
                'language': self.language,
                'tokens': tokens,
                'ast': None,  # Simplified - AST parsing requires tree-sitter
                'lines': content.splitlines(),
                'hash': self._get_file_hash(content),
                'metadata': {
                    'has_syntax_error': False,
                    'methods': methods,
                    'classes': classes,
                    'structs': structs,
                    'interfaces': interfaces,
                    'enums': enums,
                    'namespaces': namespaces,
                    'usings': usings
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
    
    def _extract_methods(self, content: str) -> List[str]:
        """
        Extract method declarations from C# code.
        
        Args:
            content: File content
            
        Returns:
            List of method names
        """
        # Match: returnType MethodName(...) or async Task MethodName(...)
        patterns = [
            r'(?:public|private|protected|internal|static|virtual|override|abstract|async)?\s*(?:void|int|bool|string|float|double|var|Task|List|[\w<>?]+)\s+(\w+)\s*\(',
        ]
        
        methods = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            methods.extend(matches)
        
        return methods
    
    def _extract_classes(self, content: str) -> List[str]:
        """
        Extract class declarations from C# code.
        
        Args:
            content: File content
            
        Returns:
            List of class names
        """
        # Match: class ClassName or public class ClassName
        pattern = r'(?:public|private|protected|internal|static|abstract|partial)?\s*class\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_structs(self, content: str) -> List[str]:
        """
        Extract struct declarations from C# code.
        
        Args:
            content: File content
            
        Returns:
            List of struct names
        """
        # Match: struct StructName
        pattern = r'(?:public|private|protected|internal)?\s*struct\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_interfaces(self, content: str) -> List[str]:
        """
        Extract interface declarations from C# code.
        
        Args:
            content: File content
            
        Returns:
            List of interface names
        """
        # Match: interface IInterfaceName
        pattern = r'(?:public|private|protected|internal)?\s*interface\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_enums(self, content: str) -> List[str]:
        """
        Extract enum declarations from C# code.
        
        Args:
            content: File content
            
        Returns:
            List of enum names
        """
        # Match: enum EnumName
        pattern = r'(?:public|private|protected|internal)?\s*enum\s+(\w+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_namespaces(self, content: str) -> List[str]:
        """
        Extract namespace declarations from C# code.
        
        Args:
            content: File content
            
        Returns:
            List of namespace names
        """
        # Match: namespace NamespaceName
        pattern = r'namespace\s+([\w.]+)'
        matches = re.findall(pattern, content)
        return matches
    
    def _extract_usings(self, content: str) -> List[str]:
        """
        Extract using statements from C# code.
        
        Args:
            content: File content
            
        Returns:
            List of using statements
        """
        # Match: using NamespaceName;
        pattern = r'using\s+([\w.]+);'
        matches = re.findall(pattern, content)
        return matches


# Register the parser with the factory
from .base_parser import ParserFactory
ParserFactory.register_parser('csharp', CSharpParser)
ParserFactory.register_parser('c#', CSharpParser)
