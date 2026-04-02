"""Phase 2: Code Normalization.

Normalizes code before parsing:
- Remove comments
- Normalize whitespace
- Optionally rename identifiers (for Type-2 clone detection)
- Standardize formatting

Input: List[IngestedFile]
Output: List[NormalizedCode]

Usage:
    from benchmark.pipeline.phases.normalize import NormalizationPhase

    phase = NormalizationPhase()
    normalized = phase.execute(ingested_files, config)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NormalizedCode:
    """Normalized code representation.
    
    Attributes:
        original_path: Path to original file.
        normalized_content: Normalized code content.
        language: Programming language.
        normalization_steps: List of normalization steps applied.
        metadata: Additional metadata.
    """
    original_path: str
    normalized_content: str
    language: str
    normalization_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        """Check if normalized code is valid."""
        return bool(self.normalized_content.strip())


class NormalizationPhase:
    """Phase 2: Code Normalization.
    
    This phase is responsible for:
    - Removing comments
    - Normalizing whitespace
    - Optionally renaming identifiers
    - Standardizing formatting
    
    Input: List[IngestedFile] from ingestion phase
    Output: List[NormalizedCode] ready for parsing
    
    Usage:
        phase = NormalizationPhase()
        normalized = phase.execute(ingested_files, config)
    """
    
    def execute(
        self,
        ingested_files: List[Any],
        config: Dict[str, Any],
    ) -> List[NormalizedCode]:
        """Execute normalization phase.
        
        Args:
            ingested_files: List of IngestedFile objects from ingestion phase.
            config: Configuration for normalization.
                - remove_comments: Remove comments (default: True)
                - normalize_whitespace: Normalize whitespace (default: True)
                - rename_identifiers: Rename identifiers (default: False)
                - preserve_strings: Preserve string literals (default: True)
            
        Returns:
            List of NormalizedCode objects.
        """
        remove_comments = config.get('remove_comments', True)
        normalize_whitespace = config.get('normalize_whitespace', True)
        rename_identifiers = config.get('rename_identifiers', False)
        preserve_strings = config.get('preserve_strings', True)
        
        results: List[NormalizedCode] = []
        
        for ingested in ingested_files:
            # Get content from ingested file
            content = getattr(ingested, 'content', str(ingested))
            language = getattr(ingested, 'language', 'unknown')
            path = str(getattr(ingested, 'path', 'unknown'))
            
            # Apply normalization steps
            steps = []
            normalized = content
            
            if remove_comments:
                normalized = self._remove_comments(normalized, language)
                steps.append('remove_comments')
            
            if normalize_whitespace:
                normalized = self._normalize_whitespace(normalized)
                steps.append('normalize_whitespace')
            
            if rename_identifiers:
                normalized = self._rename_identifiers(normalized, language)
                steps.append('rename_identifiers')
            
            results.append(NormalizedCode(
                original_path=path,
                normalized_content=normalized,
                language=language,
                normalization_steps=steps,
                metadata={'original_size': len(content)},
            ))
        
        return results
    
    def _remove_comments(self, code: str, language: str) -> str:
        """Remove comments from code.
        
        Args:
            code: Source code string.
            language: Programming language.
            
        Returns:
            Code with comments removed.
        """
        if language == 'python':
            # Remove single-line comments
            code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
            # Remove multi-line comments (docstrings)
            code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
            code = re.sub(r"'''.*?'''", '', code, flags=re.DOTALL)
        
        elif language in ['java', 'javascript', 'typescript', 'c', 'cpp', 'csharp', 'go', 'swift', 'kotlin', 'rust', 'scala']:
            # Remove single-line comments
            code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
            # Remove multi-line comments
            code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        
        elif language in ['ruby', 'perl', 'r', 'bash']:
            # Remove single-line comments
            code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        
        elif language == 'sql':
            # Remove single-line comments
            code = re.sub(r'--.*$', '', code, flags=re.MULTILINE)
            # Remove multi-line comments
            code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        
        return code
    
    def _normalize_whitespace(self, code: str) -> str:
        """Normalize whitespace in code.
        
        Args:
            code: Source code string.
            
        Returns:
            Code with normalized whitespace.
        """
        # Replace multiple spaces with single space
        code = re.sub(r' +', ' ', code)
        # Remove trailing whitespace from lines
        code = re.sub(r' +$', '', code, flags=re.MULTILINE)
        # Normalize line endings
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        # Remove empty lines (keep at most one)
        code = re.sub(r'\n{3,}', '\n\n', code)
        return code.strip()
    
    def _rename_identifiers(self, code: str, language: str) -> str:
        """Rename identifiers for Type-2 clone detection.
        
        This renames variables and functions to canonical names
        to detect clones that differ only in identifier names.
        
        Args:
            code: Source code string.
            language: Programming language.
            
        Returns:
            Code with identifiers renamed.
        """
        # Extract identifiers
        identifiers = set(re.findall(r'\b[a-zA-Z_]\w*\b', code))
        
        # Remove keywords
        keywords = self._get_keywords(language)
        identifiers -= keywords
        
        # Create mapping
        mapping = {}
        for i, identifier in enumerate(sorted(identifiers)):
            mapping[identifier] = f'v_{i}'
        
        # Replace identifiers
        for old, new in mapping.items():
            code = re.sub(r'\b' + re.escape(old) + r'\b', new, code)
        
        return code
    
    def _get_keywords(self, language: str) -> set:
        """Get language keywords.
        
        Args:
            language: Programming language.
            
        Returns:
            Set of keywords for the language.
        """
        if language == 'python':
            return {
                'False', 'None', 'True', 'and', 'as', 'assert', 'async',
                'await', 'break', 'class', 'continue', 'def', 'del', 'elif',
                'else', 'except', 'finally', 'for', 'from', 'global', 'if',
                'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or',
                'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
            }
        elif language == 'java':
            return {
                'abstract', 'assert', 'boolean', 'break', 'byte', 'case',
                'catch', 'char', 'class', 'const', 'continue', 'default',
                'do', 'double', 'else', 'enum', 'extends', 'final', 'finally',
                'float', 'for', 'goto', 'if', 'implements', 'import',
                'instanceof', 'int', 'interface', 'long', 'native', 'new',
                'package', 'private', 'protected', 'public', 'return', 'short',
                'static', 'strictfp', 'super', 'switch', 'synchronized', 'this',
                'throw', 'throws', 'transient', 'try', 'void', 'volatile', 'while',
            }
        # Add more languages as needed
        return set()