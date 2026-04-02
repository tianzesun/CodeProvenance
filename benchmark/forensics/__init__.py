"""Forensics module for code similarity detection.

Provides forensic intelligence for similarity detection:
- Causal analysis: Root cause attribution and improvement ranking
- Attribution: Error categorization and failure pattern detection
- Clone taxonomy: Clone type classification and technique detection
- Visualizations: Token heatmaps, AST alignment, causal graphs

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
from benchmark.forensics.clone_taxonomy import (
    CloneTypeClassifier,
    TechniqueDetector,
    TechniqueType,
)
from benchmark.forensics.visualizations import (
    TokenHeatmapGenerator,
    ASTAlignmentVisualizer,
    CausalGraphGenerator,
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
    # Clone taxonomy
    "CloneTypeClassifier",
    "TechniqueDetector",
    "TechniqueType",
    # Visualizations
    "TokenHeatmapGenerator",
    "ASTAlignmentVisualizer",
    "CausalGraphGenerator",
]