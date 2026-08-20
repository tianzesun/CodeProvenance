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
from benchmark.analysis.error_attribution import (
    AttributionReport,
    CloneTypeAttribution,
    ComponentEffectiveness,
    ErrorAttribution,
    ErrorAttributionModel,
)

# Legacy imports for backward compatibility
from benchmark.analysis.failure_analysis import (
    FailureAnalyzer,
    FailureCase,
    FailureCategory,
    FailureReport,
    failure_to_improvement_map,
)
from benchmark.analysis.stability_analysis import (
    FailureCluster,
    FailureClusterAnalyzer,
    FailureClusterReport,
    ThresholdStabilityAnalyzer,
    ThresholdStabilityReport,
)

from benchmark.forensics.attribution import (
    ErrorAnalyzer,
    ErrorCategory,
    ErrorReport,
    FailurePattern,
    FailurePatternDetector,
    FailurePatternReport,
)
from benchmark.forensics.causal import (
    CausalRankingEngine,
    CausalRankingReport,
    ImprovementCandidate,
    RootCause,
    RootCauseAttributor,
)
from benchmark.forensics.clone_taxonomy import (
    CloneType,
    CloneTypeClassifier,
    CloneTypeReport,
    TechniqueDetector,
    TechniqueReport,
    TechniqueType,
)

__all__ = [
    "AttributionReport",
    # Forensics - Causal analysis
    "CausalRankingEngine",
    "CausalRankingReport",
    "CloneType",
    "CloneTypeAttribution",
    # Forensics - Clone taxonomy
    "CloneTypeClassifier",
    "CloneTypeReport",
    "ComponentEffectiveness",
    # Forensics - Attribution
    "ErrorAnalyzer",
    "ErrorAttribution",
    # Legacy - Error attribution
    "ErrorAttributionModel",
    "ErrorCategory",
    "ErrorReport",
    # Legacy - Failure analysis
    "FailureAnalyzer",
    "FailureCase",
    "FailureCategory",
    "FailureCluster",
    "FailureClusterAnalyzer",
    "FailureClusterReport",
    "FailurePattern",
    "FailurePatternDetector",
    "FailurePatternReport",
    "FailureReport",
    "ImprovementCandidate",
    "RootCause",
    "RootCauseAttributor",
    "TechniqueDetector",
    "TechniqueReport",
    "TechniqueType",
    # Legacy - Stability and clustering
    "ThresholdStabilityAnalyzer",
    "ThresholdStabilityReport",
    "failure_to_improvement_map",
]
