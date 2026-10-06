"""Compatibility exports for the legacy analyzer API."""

from .batch_analyzer import (
    BatchAnalysisResult,
    BatchAnalyzer,
    analyze_batch,
)
from .code_analyzer import (
    CodeAnalysisResult,
    CodeAnalyzer,
    CodeComparisonResult,
    analyze_single_code,
    compare_two_codes,
)

__all__ = [
    "BatchAnalysisResult",
    "BatchAnalyzer",
    "CodeAnalysisResult",
    "CodeAnalyzer",
    "CodeComparisonResult",
    "analyze_batch",
    "analyze_single_code",
    "compare_two_codes",
]
