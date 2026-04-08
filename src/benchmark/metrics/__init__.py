"""Compatibility exports for legacy benchmark metrics imports."""

from src.benchmark.metrics.significance import (
    EngineComparisonResult,
    McNemarResult,
    add_significance_to_results,
    bootstrap_confidence_interval,
    compare_engines,
    mcnemar_test,
)

__all__ = [
    "EngineComparisonResult",
    "McNemarResult",
    "add_significance_to_results",
    "bootstrap_confidence_interval",
    "compare_engines",
    "mcnemar_test",
]
