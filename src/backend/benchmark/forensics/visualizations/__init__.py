"""Visualizations module for code similarity detection.

Provides publication-ready visualizations:
- TokenHeatmapGenerator: Token-level similarity heatmaps
- ASTAlignmentVisualizer: AST alignment diagrams
- CausalGraphGenerator: Causal similarity graphs
"""
from src.backend.benchmark.forensics.visualizations.heatmaps import (
    TokenHeatmapGenerator,
    HeatmapConfig,
)
from src.backend.benchmark.forensics.visualizations.ast_alignment import (
    ASTAlignmentVisualizer,
    AlignmentConfig,
)
from src.backend.benchmark.forensics.visualizations.causal_graphs import (
    CausalGraphGenerator,
    GraphConfig,
)

__all__ = [
    # Heatmaps
    "TokenHeatmapGenerator",
    "HeatmapConfig",
    # AST alignment
    "ASTAlignmentVisualizer",
    "AlignmentConfig",
    # Causal graphs
    "CausalGraphGenerator",
    "GraphConfig",
]