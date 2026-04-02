"""
Token-based Intermediate Representation.

Provides sequence-based representation of code using tokens.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from src.core.ir.base_ir import BaseIR, IRMetadata


@dataclass
class Token:
    """Represents a single token in the code.
    
    Attributes:
        token_type: Type of token (e.g., 'KEYWORD', 'IDENTIFIER', 'OPERATOR', 'LITERAL')
        value: String value of the token
        line: Line number where token appears (1-indexed)
        column: Column number where token starts (0-indexed)
        normalized: Normalized form (e.g., all identifiers become 'ID')
    """
    token_type: str
    value: str
    line: int = 0
    column: int = 0
    normalized: str = ""
    
    def __post_init__(self):
        """Set normalized value if not provided."""
        if not self.normalized:
            self.normalized = self._normalize()
    
    def _normalize(self) -> str:
        """Normalize token value.
        
        Identifiers become 'ID', literals become their type.
        """
        if self.token_type == "IDENTIFIER":
            return "ID"
        elif self.token_type == "STRING":
            return "STRING_LITERAL"
        elif self.token_type == "NUMBER":
            return "NUMBER_LITERAL"
        elif self.token_type == "BOOLEAN":
            return "BOOLEAN_LITERAL"
        elif self.token_type == "NULL":
            return "NULL_LITERAL"
        else:
            return self.value
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize token to dictionary."""
        return {
            "token_type": self.token_type,
            "value": self.value,
            "line": self.line,
            "column": self.column,
            "normalized": self.normalized,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Token':
        """Deserialize token from dictionary."""
        return cls(
            token_type=data["token_type"],
            value=data["value"],
            line=data.get("line", 0),
            column=data.get("column", 0),
            normalized=data.get("normalized", ""),
        )
    
    def __repr__(self) -> str:
        """String representation of token."""
        if self.value != self.normalized:
            return f"Token({self.token_type}, '{self.value}' → '{self.normalized}')"
        return f"Token({self.token_type}, '{self.value}')"


class TokenIR(BaseIR):
    """Token-based intermediate representation.
    
    Represents code as a sequence of tokens, useful for
    fingerprinting and winnowing algorithms.
    """
    
    def __init__(self, tokens: List[Token], metadata: IRMetadata):
        """Initialize Token IR.
        
        Args:
            tokens: List of tokens
            metadata: IR metadata
        """
        super().__init__(metadata)
        self.tokens = tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize Token IR to dictionary."""
        return {
            "tokens": [token.to_dict() for token in self.tokens],
            "token_count": len(self.tokens),
            "unique_token_types": list(self.get_unique_types()),
            "unique_values": list(self.get_unique_values()),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenIR':
        """Deserialize Token IR from dictionary.
        
        Note: This creates a placeholder. Use from_source() for actual tokenization.
        """
        # Create placeholder metadata
        metadata = IRMetadata(
            language="unknown",
            source_hash="",
            timestamp="",
            representation_type="token",
        )
        
        # Create placeholder tokens
        tokens = []
        
        instance = cls(tokens=tokens, metadata=metadata)
        return instance
    
    def _load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load Token-specific data from dictionary."""
        self.tokens = [Token.from_dict(t) for t in data["tokens"]]
    
    def validate(self) -> bool:
        """Validate Token IR integrity."""
        if not self.metadata.validate():
            return False
        
        if not isinstance(self.tokens, list):
            return False
        
        # Check that all tokens are valid
        for token in self.tokens:
            if not isinstance(token, Token):
                return False
        
        return True
    
    @classmethod
    def from_source(
        cls,
        source_code: str,
        language: str,
        file_path: Optional[str] = None
    ) -> 'TokenIR':
        """Create Token IR from source code.
        
        Args:
            source_code: Source code to tokenize
            language: Programming language
            file_path: Optional path to source file
            
        Returns:
            TokenIR instance
            
        Raises:
            ValueError: If language is not supported
        """
        # Create metadata
        metadata = cls.create_metadata(source_code, language, "token", file_path)
        
        # Tokenize source code
        tokens = cls._tokenize(source_code, language)
        
        return cls(tokens=tokens, metadata=metadata)
    
    @staticmethod
    def _tokenize(source_code: str, language: str) -> List[Token]:
        """Tokenize source code.
        
        Args:
            source_code: Source code to tokenize
            language: Programming language
            
        Returns:
            List of tokens
            
        Raises:
            ValueError: If language is not supported
        """
        if language == "python":
            return TokenIR._tokenize_python(source_code)
        elif language == "java":
            return TokenIR._tokenize_java(source_code)
        elif language == "javascript":
            return TokenIR._tokenize_javascript(source_code)
        else:
            raise ValueError(f"Unsupported language: {language}")
    
    @staticmethod
    def _tokenize_python(source_code: str) -> List[Token]:
        """Tokenize Python source code.
        
        Uses Python's built-in tokenize module.
        """
        try:
            import tokenize
            import io
        except ImportError:
            raise ImportError("Python tokenize module not available")
        
        tokens = []
        try:
            # Tokenize the source code
            for tok in tokenize.generate_tokens(io.StringIO(source_code).readline):
                token_type = tokenize.tok_name[tok.type]
                value = tok.string
                line = tok.start[0]
                column = tok.start[1]
                
                # Skip comments and whitespace
                if token_type in ['COMMENT', 'NL', 'NEWLINE', 'INDENT', 'DEDENT']:
                    continue
                
                tokens.append(Token(
                    token_type=token_type,
                    value=value,
                    line=line,
                    column=column,
                ))
        except tokenize.TokenError:
            # If tokenization fails, fall back to simple tokenization
            return TokenIR._simple_tokenize(source_code)
        
        return tokens
    
    @staticmethod
    def _simple_tokenize(source_code: str) -> List[Token]:
        """Simple tokenization fallback.
        
        Splits on whitespace and punctuation.
        """
        import re
        
        tokens = []
        lines = source_code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Simple pattern: words, numbers, operators, punctuation
            pattern = r'(\w+|[0-9]+|[+\-*/=<>!&|^~%]+|[^\w\s])'
            matches = re.finditer(pattern, line)
            
            for match in matches:
                value = match.group()
                column = match.start()
                
                # Determine token type
                if value.isdigit() or (value[0] == '-' and value[1:].isdigit()):
                    token_type = "NUMBER"
                elif value in ['+', '-', '*', '/', '=', '<', '>', '!', '&', '|', '^', '~', '%']:
                    token_type = "OPERATOR"
                elif value in ['(', ')', '[', ']', '{', '}', ',', '.', ':', ';']:
                    token_type = "PUNCTUATION"
                elif value in ['if', 'else', 'for', 'while', 'def', 'class', 'return', 'import', 'from', 'True', 'False', 'None']:
                    token_type = "KEYWORD"
                else:
                    token_type = "IDENTIFIER"
                
                tokens.append(Token(
                    token_type=token_type,
                    value=value,
                    line=line_num,
                    column=column,
                ))
        
        return tokens
    
    @staticmethod
    def _tokenize_java(source_code: str) -> List[Token]:
        """Tokenize Java source code.
        
        Uses simple pattern matching.
        """
        import re
        
        tokens = []
        lines = source_code.split('\n')
        
        # Java keywords
        keywords = {
            'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch',
            'char', 'class', 'const', 'continue', 'default', 'do', 'double',
            'else', 'enum', 'extends', 'final', 'finally', 'float', 'for',
            'goto', 'if', 'implements', 'import', 'instanceof', 'int',
            'interface', 'long', 'native', 'new', 'package', 'private',
            'protected', 'public', 'return', 'short', 'static', 'strictfp',
            'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
            'transient', 'try', 'void', 'volatile', 'while', 'true', 'false', 'null'
        }
        
        for line_num, line in enumerate(lines, 1):
            # Pattern: words, numbers, operators, punctuation
            pattern = r'(\w+|[0-9]+(\.[0-9]+)?|[+\-*/=<>!&|^~%]+|[^\w\s])'
            matches = re.finditer(pattern, line)
            
            for match in matches:
                value = match.group()
                column = match.start()
                
                # Determine token type
                if value.isdigit() or (value[0] == '-' and value[1:].isdigit()):
                    token_type = "NUMBER"
                elif value in keywords:
                    token_type = "KEYWORD"
                elif value in ['+', '-', '*', '/', '=', '<', '>', '!', '&', '|', '^', '~', '%']:
                    token_type = "OPERATOR"
                elif value in ['(', ')', '[', ']', '{', '}', ',', '.', ':', ';']:
                    token_type = "PUNCTUATION"
                else:
                    token_type = "IDENTIFIER"
                
                tokens.append(Token(
                    token_type=token_type,
                    value=value,
                    line=line_num,
                    column=column,
                ))
        
        return tokens
    
    @staticmethod
    def _tokenize_javascript(source_code: str) -> List[Token]:
        """Tokenize JavaScript source code.
        
        Uses simple pattern matching.
        """
        import re
        
        tokens = []
        lines = source_code.split('\n')
        
        # JavaScript keywords
        keywords = {
            'async', 'await', 'break', 'case', 'catch', 'class', 'const',
            'continue', 'debugger', 'default', 'delete', 'do', 'else',
            'export', 'extends', 'finally', 'for', 'function', 'if',
            'import', 'in', 'instanceof', 'let', 'new', 'return', 'super',
            'switch', 'this', 'throw', 'try', 'typeof', 'var', 'void',
            'while', 'with', 'yield', 'true', 'false', 'null', 'undefined'
        }
        
        for line_num, line in enumerate(lines, 1):
            # Pattern: words, numbers, operators, punctuation
            pattern = r'(\w+|[0-9]+(\.[0-9]+)?|[+\-*/=<>!&|^~%]+|[^\w\s])'
            matches = re.finditer(pattern, line)
            
            for match in matches:
                value = match.group()
                column = match.start()
                
                # Determine token type
                if value.isdigit() or (value[0] == '-' and value[1:].isdigit()):
                    token_type = "NUMBER"
                elif value in keywords:
                    token_type = "KEYWORD"
                elif value in ['+', '-', '*', '/', '=', '<', '>', '!', '&', '|', '^', '~', '%']:
                    token_type = "OPERATOR"
                elif value in ['(', ')', '[', ']', '{', '}', ',', '.', ':', ';']:
                    token_type = "PUNCTUATION"
                else:
                    token_type = "IDENTIFIER"
                
                tokens.append(Token(
                    token_type=token_type,
                    value=value,
                    line=line_num,
                    column=column,
                ))
        
        return tokens
    
    def get_unique_types(self) -> Set[str]:
        """Get unique token types."""
        return {token.token_type for token in self.tokens}
    
    def get_unique_values(self) -> Set[str]:
        """Get unique token values."""
        return {token.value for token in self.tokens}
    
    def get_normalized_sequence(self) -> List[str]:
        """Get sequence of normalized token values.
        
        Useful for fingerprinting and comparison.
        """
        return [token.normalized for token in self.tokens]
    
    def get_token_type_counts(self) -> Dict[str, int]:
        """Get count of each token type."""
        counts: Dict[str, int] = {}
        for token in self.tokens:
            counts[token.token_type] = counts.get(token.token_type, 0) + 1
        return counts
    
    def filter_by_type(self, token_types: Set[str]) -> 'TokenIR':
        """Filter tokens by type.
        
        Args:
            token_types: Set of token types to keep
            
        Returns:
            New TokenIR with filtered tokens
        """
        filtered_tokens = [t for t in self.tokens if t.token_type in token_types]
        return TokenIR(tokens=filtered_tokens, metadata=self.metadata)
    
    def get_ngrams(self, n: int = 3) -> List[List[str]]:
        """Get n-grams of normalized tokens.
        
        Args:
            n: Size of n-grams
            
        Returns:
            List of n-grams (each n-gram is a list of normalized tokens)
        """
        normalized = self.get_normalized_sequence()
        ngrams = []
        for i in range(len(normalized) - n + 1):
            ngrams.append(normalized[i:i+n])
        return ngrams
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the tokens."""
        type_counts = self.get_token_type_counts()
        
        return {
            "total_tokens": len(self.tokens),
            "unique_types": len(self.get_unique_types()),
            "unique_values": len(self.get_unique_values()),
            "type_counts": type_counts,
            "lines_spanned": max((t.line for t in self.tokens), default=0),
        }
    
    def __repr__(self) -> str:
        """String representation of Token IR."""
        stats = self.get_statistics()
        return f"TokenIR(tokens={stats['total_tokens']}, types={stats['unique_types']}, language={self.metadata.language})"
    
    def __len__(self) -> int:
        """Get number of tokens."""
        return len(self.tokens)
    
    def __iter__(self):
        """Iterate over tokens."""
        return iter(self.tokens)
    
    def __getitem__(self, index: int) -> Token:
        """Get token by index."""
        return self.tokens[index]