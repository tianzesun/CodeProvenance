"""Attribution module for code similarity detection.

Provides error categorization and failure pattern detection:
- ErrorAnalyzer: Categorizes errors by type and characteristics
- FailurePatternDetector: Detects common failure patterns
"""
from benchmark.forensics.attribution.error_analysis import (
    ErrorAnalyzer,
    ErrorCategory,
    ErrorReport,
)
from benchmark.forensics.attribution.failure_patterns import (
    FailurePatternDetector,
    FailurePattern,
    FailurePatternReport,
)

__all__ = [
    # Error analysis
    "ErrorAnalyzer",
    "ErrorCategory",
    "ErrorReport",
    # Failure patterns
    "FailurePatternDetector",
    "FailurePattern",
    "FailurePatternReport",
]