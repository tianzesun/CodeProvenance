"""Benchmark analysis module.

Provides diagnostic intelligence for similarity detection:
- Failure analysis: Categorize failures by type and characteristic
- Error attribution: Per-pair decomposition of score errors
- Threshold stability: Robustness analysis across threshold range
- Failure clustering: Group similar failure patterns into attack surfaces
"""
from benchmark.analysis.failure_analysis import (
    FailureAnalyzer,
    FailureCase,
    FailureCategory,
    FailureReport,
    failure_to_improvement_map,
)
from benchmark.analysis.error_attribution import (
    ErrorAttributionModel,
    ErrorAttribution,
    AttributionReport,
    ComponentEffectiveness,
    CloneTypeAttribution,
)
from benchmark.analysis.stability_analysis import (
    ThresholdStabilityAnalyzer,
    FailureClusterAnalyzer,
    ThresholdStabilityReport,
    FailureClusterReport,
    FailureCluster,
)

__all__ = [
    # Failure analysis
    "FailureAnalyzer",
    "FailureCase",
    "FailureCategory",
    "FailureReport",
    "failure_to_improvement_map",
    # Error attribution
    "ErrorAttributionModel",
    "ErrorAttribution",
    "AttributionReport",
    "ComponentEffectiveness",
    "CloneTypeAttribution",
    # Stability and clustering
    "ThresholdStabilityAnalyzer",
    "FailureClusterAnalyzer",
    "ThresholdStabilityReport",
    "FailureClusterReport",
    "FailureCluster",
]