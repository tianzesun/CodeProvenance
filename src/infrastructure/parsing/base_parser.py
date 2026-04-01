"""
Base parser class for code file parsing.

All language-specific parsers should inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import hashlib
from pathlib import Path


class BaseParser(ABC):
    """
    Abstract base class for code parsers.
    
    Each language-specific parser should implement the parse method
    to extract tokens, AST nodes, or other representations suitable
    for similarity comparison.
    """
    
    def __init__(self):
        self.language = self.__class__.__name__.replace('Parser', '').lower()
    
    @abstractmethod
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a code file and return a structured representation.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing parsed representation including:
            - tokens: List of tokens
            - ast: Abstract Syntax Tree (if applicable)
            - lines: List of lines
            - hash: Content hash for change detection
            - metadata: Additional language-specific metadata
        """
        pass
    
    def _get_file_hash(self, content: str) -> str:
        """
        Generate SHA256 hash of file content.
        
        Args:
            content: File content
            
        Returns:
            Hexadecimal SHA256 hash
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _tokenize_basic(self, content: str) -> List[str]:
        """
        Basic tokenization by splitting on whitespace and punctuation.
        This is a fallback for languages without specific tokenizers.
        
        Args:
            content: File content
            
        Returns:
            List of tokens
        """
        import re
        # Split on whitespace and common punctuation
        tokens = re.findall(r'\b\w+\b|[^\w\s]', content)
        return [token for token in tokens if token.strip()]
    
    def get_language(self) -> str:
        """
        Get the language this parser handles.
        
        Returns:
            Language identifier string
        """
        return self.language


class ParserFactory:
    """
    Factory class for creating language-specific parsers.
    """
    
    _parsers = {}
    
    @classmethod
    def register_parser(cls, language: str, parser_class):
        """
        Register a parser for a specific language.
        
        Args:
            language: Language identifier (e.g., 'python', 'java')
            parser_class: Parser class to register
        """
        cls._parsers[language.lower()] = parser_class
    
    @classmethod
    def get_parser(cls, language: str) -> Optional[BaseParser]:
        """
        Get a parser for the specified language.
        
        Args:
            language: Language identifier
            
        Returns:
            Parser instance or None if not found
        """
        parser_class = cls._parsers.get(language.lower())
        if parser_class:
            return parser_class()
        return None
    
    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """
        Get list of supported languages.
        
        Returns:
            List of language identifiers
        """
        return list(cls._parsers.keys())