"""Compatibility exports for the legacy processor API."""

from .code_processor import (
    CodeProcessingResult,
    CodeProcessor,
    detect_language,
    process_code,
)
from .submission_processor import (
    SubmissionProcessingResult,
    SubmissionProcessor,
    process_submission,
)

__all__ = [
    "CodeProcessingResult",
    "CodeProcessor",
    "SubmissionProcessingResult",
    "SubmissionProcessor",
    "detect_language",
    "process_code",
    "process_submission",
]
