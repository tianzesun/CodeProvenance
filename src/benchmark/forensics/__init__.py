"""Forensics module for code similarity detection.

Provides forensic intelligence for similarity detection:
- Causal analysis: Root cause attribution and improvement ranking
- Attribution: Error categorization and failure pattern detection
- Clone taxonomy: Clone type classification and technique detection
- Visualizations: Token heatmaps, AST alignment, causal graphs
- Stability analysis: Threshold stability and failure clustering

This module elevates analysis to forensics by providing:
- Strategic intelligence for detector improvement
- Publication-ready visualizations
- Explainability features for forensic analysis
- Clear forensic purpose and structure
"""
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
    FailurePatternDetector,
    FailurePattern,
)
from benchmark.forensics.attribution.error_attribution import (
    ErrorAttributionModel,
    ErrorAttributionReport,
)
from benchmark.forensics.clone_taxonomy import (
    CloneTypeClassifier,
    CloneType,
    CloneTypeReport,
)
from benchmark.forensics.visualizations import (
    TokenHeatmapGenerator,
    ASTAlignmentVisualizer,
    CausalGraphGenerator,
)
from benchmark.forensics.stability_analysis import (
    ThresholdStabilityAnalyzer,
    FailureClusterAnalyzer,
    StabilityReport,
    ClusterReport,
    FailureCluster,
)
from benchmark.forensics.clone_type_breakdown import (
    CloneTypeBreakdown,
    analyze_clone_type_breakdown,
)

__all__ = [
    # Causal analysis
    "CausalRankingEngine",
    "CausalRankingReport",
    "ImprovementCandidate",
    "RootCauseAttributor",
    "RootCause",
    # Attribution
    "ErrorAnalyzer",
    "ErrorCategory",
    "FailurePatternDetector",
    "FailurePattern",
    "ErrorAttributionModel",
    "ErrorAttributionReport",
    # Clone taxonomy
    "CloneTypeClassifier",
    "TechniqueDetector",
    "TechniqueType",
    # Visualizations
    "TokenHeatmapGenerator",
    "ASTAlignmentVisualizer",
    "CausalGraphGenerator",
    # Stability analysis
    "ThresholdStabilityAnalyzer",
    "FailureClusterAnalyzer",
    "StabilityReport",
    "ClusterReport",
    "FailureCluster",
]
