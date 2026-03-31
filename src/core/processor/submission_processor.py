"""
Submission Processor for CodeProvenance.

Handles processing of code submissions for similarity detection.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib
import json

from .code_processor import CodeProcessor, ProcessingResult


@dataclass
class SubmissionProcessingResult:
    """Result of processing a submission."""
    submission_id: str
    file_path: str
    language: str
    processing_result: ProcessingResult
    fingerprint: str
    metadata: Dict[str, Any]
    processing_time: float
    timestamp: str


class SubmissionProcessor:
    """
    Processes code submissions for similarity detection.
    
    Features:
    - Submission validation
    - Language detection
    - Code processing
    - Fingerprint generation
    - Metadata extraction
    """
    
    def __init__(
        self,
        code_processor: Optional[CodeProcessor] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        supported_languages: Optional[List[str]] = None
    ):
        """
        Initialize submission processor.
        
        Args:
            code_processor: CodeProcessor instance
            max_file_size: Maximum file size in bytes
            supported_languages: List of supported languages
        """
        self.code_processor = code_processor or CodeProcessor()
        self.max_file_size = max_file_size
        self.supported_languages = supported_languages or [
            'python', 'java', 'javascript', 'typescript',
            'c', 'cpp', 'csharp', 'go', 'rust', 'ruby', 'php'
        ]
    
    def process_submission(
        self,
        submission_id: str,
        file_path: str,
        code: str,
        language: str = 'auto',
        metadata: Optional[Dict[str, Any]] = None
    ) -> SubmissionProcessingResult:
        """
        Process a single code submission.
        
        Args:
            submission_id: Unique submission identifier
            file_path: File path
            code: Source code
            language: Programming language ('auto' for detection)
            metadata: Additional metadata
            
        Returns:
            SubmissionProcessingResult
        """
        import time
        start_time = time.time()
        
        # Validate submission
        self._validate_submission(code, file_path)
        
        # Detect language if auto
        if language == 'auto':
            language = self._detect_language(code, file_path)
        
        # Process code
        processing_result = self.code_processor.process(code, language)
        
        # Generate fingerprint
        fingerprint = self._generate_fingerprint(processing_result)
        
        # Calculate metadata
        result_metadata = self._extract_metadata(
            submission_id,
            file_path,
            code,
            processing_result,
            metadata
        )
        
        processing_time = time.time() - start_time
        
        return SubmissionProcessingResult(
            submission_id=submission_id,
            file_path=file_path,
            language=language,
            processing_result=processing_result,
            fingerprint=fingerprint,
            metadata=result_metadata,
            processing_time=processing_time,
            timestamp=datetime.now().isoformat()
        )
    
    def process_submissions(
        self,
        submissions: Dict[str, Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, SubmissionProcessingResult]:
        """
        Process multiple submissions.
        
        Args:
            submissions: Dictionary mapping submission_id to submission data (or code string)
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary mapping submission_id to result
        """
        results = {}
        total = len(submissions)
        
        for i, (submission_id, data) in enumerate(submissions.items()):
            # Handle both dict and string formats
            if isinstance(data, dict):
                file_path = data.get('file_path', 'unknown')
                code = data.get('code', '')
                language = data.get('language', 'auto')
                metadata = data.get('metadata')
            else:
                # Assume data is the code string
                file_path = 'unknown'
                code = str(data)
                language = 'auto'
                metadata = None
            
            result = self.process_submission(
                submission_id=submission_id,
                file_path=file_path,
                code=code,
                language=language,
                metadata=metadata
            )
            results[submission_id] = result
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def process_directory(
        self,
        directory_path: str,
        file_pattern: str = '*.py',
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, SubmissionProcessingResult]:
        """
        Process all code files in a directory.
        
        Args:
            directory_path: Path to directory
            file_pattern: File pattern to match
            recursive: Whether to search recursively
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary mapping submission_id to result
        """
        path = Path(directory_path)
        
        if not path.exists():
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Find all matching files
        if recursive:
            files = list(path.rglob(file_pattern))
        else:
            files = list(path.glob(file_pattern))
        
        # Create submissions dictionary
        submissions = {}
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                relative_path = str(file_path.relative_to(path))
                submission_id = hashlib.md5(relative_path.encode()).hexdigest()[:8]
                
                # Detect language from extension
                ext = file_path.suffix.lower()
                language_map = {
                    '.py': 'python',
                    '.java': 'java',
                    '.js': 'javascript',
                    '.ts': 'typescript',
                    '.c': 'c',
                    '.cpp': 'cpp',
                    '.go': 'go',
                    '.rs': 'rust',
                }
                language = language_map.get(ext, 'auto')
                
                submissions[submission_id] = {
                    'file_path': relative_path,
                    'code': content,
                    'language': language,
                    'metadata': {
                        'original_path': str(file_path),
                        'file_size': len(content),
                    }
                }
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")
        
        return self.process_submissions(submissions, progress_callback)
    
    def _validate_submission(self, code: str, file_path: str):
        """Validate a code submission."""
        # Check file size
        if len(code) > self.max_file_size:
            raise ValueError(
                f"File too large: {len(code)} bytes "
                f"(max: {self.max_file_size} bytes)"
            )
        
        # Check if code is empty
        if not code.strip():
            raise ValueError("Code submission is empty")
    
    def _detect_language(self, code: str, file_path: str) -> str:
        """Detect programming language."""
        # Check file extension
        if file_path != 'unknown':
            ext = Path(file_path).suffix.lower()
            extension_map = {
                '.py': 'python',
                '.java': 'java',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.c': 'c',
                '.cpp': 'cpp',
                '.cs': 'csharp',
                '.go': 'go',
                '.rs': 'rust',
                '.rb': 'ruby',
                '.php': 'php',
            }
            if ext in extension_map:
                return extension_map[ext]
        
        # Simple heuristic based on code patterns
        if 'def ' in code or 'import ' in code or 'class ' in code:
            if ':' in code and '->' in code:
                return 'python'
            elif '{' in code and '}' in code:
                return 'java'
        
        # Default
        return 'python'
    
    def _generate_fingerprint(self, processing_result: ProcessingResult) -> str:
        """Generate a fingerprint for the processed code."""
        # Use normalized code for fingerprint
        normalized = processing_result.normalized_code
        
        # Generate hash
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()
        
        return fingerprint
    
    def _extract_metadata(
        self,
        submission_id: str,
        file_path: str,
        code: str,
        processing_result: ProcessingResult,
        additional_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract metadata from submission."""
        metadata = {
            'submission_id': submission_id,
            'file_path': file_path,
            'language': processing_result.language,
            'original_size': len(code),
            'processed_size': len(processing_result.processed_code),
            'line_count': len(processing_result.lines),
            'token_count': len(processing_result.tokens),
            'processing_time': processing_result.processing_time,
            'original_hash': processing_result.metadata.get('original_hash'),
            'processed_hash': processing_result.metadata.get('processed_hash'),
        }
        
        # Add additional metadata if provided
        if additional_metadata:
            metadata.update(additional_metadata)
        
        return metadata
    
    def compare_fingerprints(
        self,
        results: Dict[str, SubmissionProcessingResult]
    ) -> List[Dict[str, Any]]:
        """
        Compare fingerprints to find exact duplicates.
        
        Args:
            results: Dictionary of submission results
            
        Returns:
            List of duplicate groups
        """
        # Group by fingerprint
        fingerprint_groups: Dict[str, List[str]] = {}
        for submission_id, result in results.items():
            fingerprint = result.fingerprint
            if fingerprint not in fingerprint_groups:
                fingerprint_groups[fingerprint] = []
            fingerprint_groups[fingerprint].append(submission_id)
        
        # Find duplicates
        duplicates = []
        for fingerprint, submission_ids in fingerprint_groups.items():
            if len(submission_ids) > 1:
                duplicates.append({
                    'fingerprint': fingerprint,
                    'submission_ids': submission_ids,
                    'count': len(submission_ids)
                })
        
        return duplicates


def process_submission(
    submission_id: str,
    file_path: str,
    code: str,
    language: str = 'auto'
) -> SubmissionProcessingResult:
    """
    Convenience function for processing a single submission.
    
    Args:
        submission_id: Unique submission identifier
        file_path: File path
        code: Source code
        language: Programming language
        
    Returns:
        SubmissionProcessingResult
    """
    processor = SubmissionProcessor()
    return processor.process_submission(submission_id, file_path, code, language)