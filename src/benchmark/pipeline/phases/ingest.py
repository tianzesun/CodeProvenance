"""Phase 1: File Ingestion.

Loads and validates input files from various sources:
- Local file paths
- Directories
- URLs
- Dataset loaders

Input: File paths or dataset identifiers
Output: List[IngestedFile] with validated content

Usage:
    from benchmark.pipeline.phases.ingest import IngestionPhase

    phase = IngestionPhase()
    files = phase.execute(["path/to/file1.py", "path/to/file2.py"], config)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import re


@dataclass
class IngestedFile:
    """A file that has been ingested and validated.
    
    Attributes:
        path: Path to the file.
        content: File content as string.
        language: Detected programming language.
        metadata: Additional metadata (size, hash, etc.).
    """
    path: Path
    content: str
    language: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def size(self) -> int:
        """File size in bytes."""
        return len(self.content.encode('utf-8'))
    
    @property
    def content_hash(self) -> str:
        """MD5 hash of content."""
        return hashlib.md5(self.content.encode('utf-8')).hexdigest()
    
    def validate(self) -> bool:
        """Validate file content.
        
        Returns:
            True if file is valid.
        """
        if not self.content:
            return False
        if not self.language or self.language == 'unknown':
            return False
        return True


class IngestionPhase:
    """Phase 1: Load and validate input files.
    
    This phase is responsible for:
    - Loading files from paths
    - Validating file existence and readability
    - Detecting programming language
    - Extracting metadata
    
    Input: List of file paths or dataset identifiers
    Output: List[IngestedFile] with validated content
    
    Usage:
        phase = IngestionPhase()
        files = phase.execute(["path/to/file1.py", "path/to/file2.py"], config)
    """
    
    # Language detection mapping
    LANGUAGE_MAP = {
        '.py': 'python',
        '.java': 'java',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.rs': 'rust',
        '.scala': 'scala',
        '.m': 'objective-c',
        '.pl': 'perl',
        '.r': 'r',
        '.sql': 'sql',
        '.sh': 'bash',
        '.bat': 'batch',
        '.ps1': 'powershell',
    }
    
    def execute(
        self,
        paths: List[str],
        config: Dict[str, Any],
    ) -> List[IngestedFile]:
        """Execute ingestion phase.
        
        Args:
            paths: List of file paths to ingest.
            config: Configuration for ingestion.
                - encoding: File encoding (default: utf-8)
                - max_size: Maximum file size in bytes (default: 10MB)
                - recursive: Whether to recursively process directories (default: False)
            
        Returns:
            List of IngestedFile objects.
        
        Raises:
            FileNotFoundError: If file not found.
            ValueError: If file is too large or invalid.
        """
        encoding = config.get('encoding', 'utf-8')
        max_size = config.get('max_size', 10 * 1024 * 1024)  # 10MB default
        recursive = config.get('recursive', False)
        
        results: List[IngestedFile] = []
        
        for path_str in paths:
            path = Path(path_str)
            
            # Handle directories
            if path.is_dir():
                if recursive:
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            ingested = self._ingest_file(
                                file_path, encoding, max_size
                            )
                            if ingested:
                                results.append(ingested)
                else:
                    for file_path in path.glob('*'):
                        if file_path.is_file():
                            ingested = self._ingest_file(
                                file_path, encoding, max_size
                            )
                            if ingested:
                                results.append(ingested)
            else:
                # Single file
                ingested = self._ingest_file(path, encoding, max_size)
                if ingested:
                    results.append(ingested)
        
        return results
    
    def _ingest_file(
        self,
        path: Path,
        encoding: str,
        max_size: int,
    ) -> Optional[IngestedFile]:
        """Ingest a single file.
        
        Args:
            path: Path to file.
            encoding: File encoding.
            max_size: Maximum file size.
            
        Returns:
            IngestedFile if successful, None otherwise.
        """
        try:
            # Check existence
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            # Check size
            file_size = path.stat().st_size
            if file_size > max_size:
                raise ValueError(
                    f"File too large: {file_size} bytes (max: {max_size})"
                )
            
            # Read content
            content = path.read_text(encoding=encoding)
            
            # Detect language
            language = self._detect_language(path)
            
            # Create metadata
            metadata = {
                'size': file_size,
                'extension': path.suffix,
                'filename': path.name,
            }
            
            return IngestedFile(
                path=path,
                content=content,
                language=language,
                metadata=metadata,
            )
        
        except Exception as e:
            # Log error but don't fail the entire phase
            print(f"Warning: Failed to ingest {path}: {e}")
            return None
    
    def _detect_language(self, path: Path) -> str:
        """Detect programming language from file extension.
        
        Args:
            path: Path to file.
            
        Returns:
            Language identifier string.
        """
        suffix = path.suffix.lower()
        return self.LANGUAGE_MAP.get(suffix, 'unknown')
    
    def validate_paths(self, paths: List[str]) -> List[str]:
        """Validate that all paths exist.
        
        Args:
            paths: List of paths to validate.
            
        Returns:
            List of valid paths.
        
        Raises:
            FileNotFoundError: If any path doesn't exist.
        """
        valid_paths = []
        for path_str in paths:
            path = Path(path_str)
            if path.exists():
                valid_paths.append(path_str)
            else:
                raise FileNotFoundError(f"Path not found: {path_str}")
        return valid_paths