"""
Code Processor for CodeProvenance.

Handles preprocessing and normalization of code for similarity detection.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import re
import hashlib


@dataclass
class ProcessingResult:
    """Result of code processing."""
    original_code: str
    processed_code: str
    normalized_code: str
    tokens: List[Dict[str, Any]]
    lines: List[str]
    language: str
    metadata: Dict[str, Any]
    processing_time: float


class CodeProcessor:
    """
    Processes code for similarity detection.
    
    Features:
    - Whitespace normalization
    - Comment removal
    - Variable name normalization
    - Token extraction
    - Language-specific preprocessing
    """
    
    def __init__(
        self,
        remove_comments: bool = True,
        normalize_whitespace: bool = True,
        normalize_variables: bool = True,
        preserve_strings: bool = True
    ):
        """
        Initialize code processor.
        
        Args:
            remove_comments: Remove comments before processing
            normalize_whitespace: Normalize whitespace
            normalize_variables: Normalize variable names
            preserve_strings: Preserve string literals
        """
        self.remove_comments = remove_comments
        self.normalize_whitespace = normalize_whitespace
        self.normalize_variables = normalize_variables
        self.preserve_strings = preserve_strings
        
        # Language-specific comment patterns
        self.comment_patterns = {
            'python': {
                'single': r'#.*$',
                'multi': r'""".*?"""',
            },
            'java': {
                'single': r'//.*$',
                'multi': r'/\*.*?\*/',
            },
            'javascript': {
                'single': r'//.*$',
                'multi': r'/\*.*?\*/',
            },
            'c': {
                'single': r'//.*$',
                'multi': r'/\*.*?\*/',
            },
            'cpp': {
                'single': r'//.*$',
                'multi': r'/\*.*?\*/',
            },
        }
    
    def process(
        self,
        code: str,
        language: str = 'unknown',
        **kwargs
    ) -> ProcessingResult:
        """
        Process code for similarity detection.
        
        Args:
            code: Source code
            language: Programming language
            
        Returns:
            ProcessingResult with processed data
        """
        import time
        start_time = time.time()
        
        # Store original
        original_code = code
        
        # Remove comments if enabled
        if self.remove_comments:
            processed_code = self._remove_comments(code, language)
        else:
            processed_code = code
        
        # Normalize whitespace if enabled
        if self.normalize_whitespace:
            processed_code = self._normalize_whitespace(processed_code)
        
        # Extract tokens
        tokens = self._extract_tokens(processed_code, language)
        
        # Normalize variables if enabled
        if self.normalize_variables:
            processed_code, tokens = self._normalize_variables(processed_code, tokens)
        
        # Get normalized code (for hashing)
        normalized_code = self._get_normalized_code(processed_code)
        
        # Split into lines
        lines = processed_code.split('\n')
        
        # Calculate metadata
        metadata = self._calculate_metadata(code, processed_code, tokens)
        
        processing_time = time.time() - start_time
        
        return ProcessingResult(
            original_code=original_code,
            processed_code=processed_code,
            normalized_code=normalized_code,
            tokens=tokens,
            lines=lines,
            language=language,
            metadata=metadata,
            processing_time=processing_time
        )
    
    def _remove_comments(self, code: str, language: str) -> str:
        """Remove comments from code."""
        patterns = self.comment_patterns.get(language, {})
        
        result = code
        
        # Remove multi-line comments first
        if 'multi' in patterns:
            result = re.sub(patterns['multi'], '', result, flags=re.DOTALL)
        
        # Remove single-line comments
        if 'single' in patterns:
            result = re.sub(patterns['single'], '', result, flags=re.MULTILINE)
        
        return result
    
    def _normalize_whitespace(self, code: str) -> str:
        """Normalize whitespace in code."""
        # Replace multiple spaces with single space
        result = re.sub(r' +', ' ', code)
        
        # Replace tabs with spaces
        result = result.replace('\t', '    ')
        
        # Remove trailing whitespace from lines
        lines = result.split('\n')
        lines = [line.rstrip() for line in lines]
        
        # Remove multiple consecutive blank lines
        normalized_lines = []
        prev_blank = False
        for line in lines:
            is_blank = not line.strip()
            if is_blank and prev_blank:
                continue
            normalized_lines.append(line)
            prev_blank = is_blank
        
        return '\n'.join(normalized_lines)
    
    def _extract_tokens(
        self,
        code: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """Extract tokens from code."""
        tokens = []
        
        # Define token patterns
        patterns = [
            (r'\b(if|else|elif|for|while|return|def|class|import|from|try|except|finally|with|as|yield|lambda|pass|break|continue|raise|assert|del|global|nonlocal)\b', 'KEYWORD'),
            (r'\b(True|False|None)\b', 'LITERAL'),
            (r'\b[a-zA-Z_]\w*\b', 'IDENTIFIER'),
            (r'\b\d+\.?\d*\b', 'NUMBER'),
            (r'["\'].*?["\']', 'STRING'),
            (r'[+\-*/%=<>!&|^~]', 'OPERATOR'),
            (r'[(){}\[\]:;,.]', 'PUNCTUATION'),
        ]
        
        # Compile patterns
        compiled_patterns = [
            (re.compile(pattern), token_type)
            for pattern, token_type in patterns
        ]
        
        # Find all matches
        for match in re.finditer('|'.join(f'(?P<{name}>{pattern})' for pattern, name in patterns), code):
            for name, value in match.groupdict().items():
                if value:
                    tokens.append({
                        'type': name,
                        'value': value,
                        'line': code[:match.start()].count('\n') + 1,
                        'position': match.start()
                    })
        
        return tokens
    
    def _normalize_variables(
        self,
        code: str,
        tokens: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Normalize variable names for renaming resistance."""
        # Reserved words to skip
        reserved = {
            'if', 'else', 'elif', 'for', 'while', 'return', 'def', 'class',
            'import', 'from', 'try', 'except', 'finally', 'with', 'as',
            'yield', 'lambda', 'pass', 'break', 'continue', 'raise', 'assert',
            'del', 'global', 'nonlocal', 'True', 'False', 'None', 'self', 'this',
            'int', 'float', 'str', 'bool', 'list', 'dict', 'set', 'tuple'
        }
        
        # Map original names to normalized names
        var_map = {}
        var_counter = [0]
        
        def normalize_name(name: str) -> str:
            """Normalize a variable name."""
            if name in reserved:
                return name
            
            # Common loop variables
            if name in ('i', 'j', 'k', 'n', 'm'):
                return 'LOOP_VAR'
            
            # Constants
            if name.isupper():
                return 'CONST'
            
            # Private variables
            if name.startswith('_'):
                return 'PRIVATE_VAR'
            
            # Generic variable
            if name not in var_map:
                var_map[name] = f'var_{var_counter[0]}'
                var_counter[0] += 1
            
            return var_map[name]
        
        # Update tokens with normalized names
        normalized_tokens = []
        for token in tokens:
            if token['type'] == 'IDENTIFIER':
                normalized_name = normalize_name(token['value'])
                normalized_tokens.append({
                    **token,
                    'value': normalized_name,
                    'original_value': token['value']
                })
            else:
                normalized_tokens.append(token)
        
        # Reconstruct code with normalized variables
        # This is simplified - in practice you'd use AST manipulation
        result = code
        for original, normalized in var_map.items():
            result = re.sub(r'\b' + re.escape(original) + r'\b', normalized, result)
        
        return result, normalized_tokens
    
    def _get_normalized_code(self, code: str) -> str:
        """Get normalized code for hashing."""
        # Remove all whitespace
        result = re.sub(r'\s+', '', code)
        
        # Convert to lowercase
        result = result.lower()
        
        return result
    
    def _calculate_metadata(
        self,
        original_code: str,
        processed_code: str,
        tokens: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate processing metadata."""
        original_lines = original_code.split('\n')
        processed_lines = processed_code.split('\n')
        
        # Token type distribution
        token_types = {}
        for token in tokens:
            token_type = token['type']
            token_types[token_type] = token_types.get(token_type, 0) + 1
        
        return {
            'original_line_count': len(original_lines),
            'processed_line_count': len(processed_lines),
            'token_count': len(tokens),
            'token_type_distribution': token_types,
            'original_hash': hashlib.sha256(original_code.encode()).hexdigest(),
            'processed_hash': hashlib.sha256(processed_code.encode()).hexdigest(),
        }
    
    def process_batch(
        self,
        submissions: Dict[str, str],
        languages: Optional[Dict[str, str]] = None
    ) -> Dict[str, ProcessingResult]:
        """
        Process multiple code submissions.
        
        Args:
            submissions: Dictionary mapping file paths to code
            languages: Optional language mappings
            
        Returns:
            Dictionary mapping file paths to ProcessingResult
        """
        results = {}
        
        for file_path, code in submissions.items():
            language = languages.get(file_path, 'unknown') if languages else 'unknown'
            results[file_path] = self.process(code, language)
        
        return results


def process_code(
    code: str,
    language: str = 'unknown',
    remove_comments: bool = True,
    normalize_whitespace: bool = True
) -> ProcessingResult:
    """
    Convenience function for code processing.
    
    Args:
        code: Source code
        language: Programming language
        remove_comments: Remove comments
        normalize_whitespace: Normalize whitespace
        
    Returns:
        ProcessingResult
    """
    processor = CodeProcessor(
        remove_comments=remove_comments,
        normalize_whitespace=normalize_whitespace
    )
    return processor.process(code, language)