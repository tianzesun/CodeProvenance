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
from src.backend.benchmark.forensics.attribution import (
    ErrorAnalyzer,
    ErrorCategory,
    FailurePattern,
    FailurePatternDetector,
)
from src.backend.benchmark.forensics.attribution.error_attribution import (
    ErrorAttributionModel,
    ErrorAttributionReport,
)
from src.backend.benchmark.forensics.causal import (
    CausalRankingEngine,
    CausalRankingReport,
    ImprovementCandidate,
    RootCause,
    RootCauseAttributor,
)
from src.backend.benchmark.forensics.clone_taxonomy import (
    CloneType,
    CloneTypeClassifier,
    CloneTypeReport,
)
from src.backend.benchmark.forensics.clone_type_breakdown import (
    CloneTypeBreakdown,
    analyze_clone_type_breakdown,
)
from src.backend.benchmark.forensics.stability_analysis import (
    ClusterReport,
    FailureCluster,
    FailureClusterAnalyzer,
    StabilityReport,
    ThresholdStabilityAnalyzer,
)
from src.backend.benchmark.forensics.visualizations import (
    ASTAlignmentVisualizer,
    CausalGraphGenerator,
    TokenHeatmapGenerator,
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
