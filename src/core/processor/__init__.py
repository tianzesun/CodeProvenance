"""Compatibility exports for the legacy processor API."""

from src.core.processor.code_processor import CodeProcessingResult, CodeProcessor, process_code
from src.core.processor.submission_processor import (
    SubmissionProcessingResult,
    SubmissionProcessor,
    process_submission,
)

__all__ = [
    "CodeProcessingResult",
    "CodeProcessor",
    "SubmissionProcessingResult",
    "SubmissionProcessor",
    "process_code",
    "process_submission",
]
