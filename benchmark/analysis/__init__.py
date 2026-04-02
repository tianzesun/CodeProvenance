"""Benchmark analysis module.

Provides diagnostic intelligence for similarity detection:
- Failure analysis: Categorize failures by type and characteristic
- Error attribution: Per-pair decomposition of score errors
- Threshold stability: Robustness analysis across threshold range
- Failure clustering: Group similar failure patterns into attack surfaces

Note: This module has been elevated to benchmark.forensics for enhanced
forensic intelligence capabilities. The original imports are maintained
for backward compatibility.
"""
# Import from forensics module for enhanced capabilities
from benchmark.forensics.causal import (
    CausalRankingEngine,
    CausalRankingReport,
    ImprovementCandidate,
    RootCauseAttributor,
    RootCause,
)
from benchmark.forensics.attribution import (
    ErrorAnalyzer,
    ErrorCategory,
    ErrorReport,
    FailurePatternDetector,
    FailurePattern,
    FailurePatternReport,
)
from benchmark.forensics.clone_taxonomy import (
    CloneTypeClassifier,
    CloneType,
    CloneTypeReport,
    TechniqueDetector,
    TechniqueType,
    TechniqueReport,
)

# Legacy imports for backward compatibility
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
    # Forensics - Causal analysis
    "CausalRankingEngine",
    "CausalRankingReport",
    "ImprovementCandidate",
    "RootCauseAttributor",
    "RootCause",
    # Forensics - Attribution
    "ErrorAnalyzer",
    "ErrorCategory",
    "ErrorReport",
    "FailurePatternDetector",
    "FailurePattern",
    "FailurePatternReport",
    # Forensics - Clone taxonomy
    "CloneTypeClassifier",
    "CloneType",
    "CloneTypeReport",
    "TechniqueDetector",
    "TechniqueType",
    "TechniqueReport",
    # Legacy - Failure analysis
    "FailureAnalyzer",
    "FailureCase",
    "FailureCategory",
    "FailureReport",
    "failure_to_improvement_map",
    # Legacy - Error attribution
    "ErrorAttributionModel",
    "ErrorAttribution",
    "AttributionReport",
    "ComponentEffectiveness",
    "CloneTypeAttribution",
    # Legacy - Stability and clustering
    "ThresholdStabilityAnalyzer",
    "FailureClusterAnalyzer",
    "ThresholdStabilityReport",
    "FailureClusterReport",
    "FailureCluster",
]
