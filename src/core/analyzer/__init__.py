"""Compatibility exports for the legacy analyzer API."""

from src.core.analyzer.batch_analyzer import BatchAnalysisResult, BatchAnalyzer, analyze_batch
from src.core.analyzer.code_analyzer import (
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
