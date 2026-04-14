"""Visualization modules for benchmark reporting.

Provides various visualization generators for code similarity analysis,
including heatmaps, AST alignment diagrams, causal graphs, and distributions.
"""
from src.backend.benchmark.reporting.visualizations.heatmaps import TokenHeatmapGenerator
from src.backend.benchmark.reporting.visualizations.ast_alignment import ASTAlignmentVisualizer
from src.backend.benchmark.reporting.visualizations.causal_graphs import CausalGraphGenerator
from src.backend.benchmark.reporting.visualizations.distributions import DistributionPlotter

__all__ = [
    'TokenHeatmapGenerator',
    'ASTAlignmentVisualizer',
    'CausalGraphGenerator',
    'DistributionPlotter'
]