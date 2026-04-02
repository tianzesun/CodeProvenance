"""Benchmark reporting module.

Provides tiered reporting (scientific, operational, forensic) and visualization
capabilities for benchmark results.
"""
from benchmark.reporting.json_writer import JSONReportWriter
from benchmark.reporting.html_report import HTMLReportWriter
from benchmark.reporting.leaderboard import Leaderboard, LeaderboardEntry

# Tiered reporting
from benchmark.reporting.tiers.scientific import ScientificReport
from benchmark.reporting.tiers.operational import OperationalReport
from benchmark.reporting.tiers.forensic import ForensicReport

# Visualizations
from benchmark.reporting.visualizations.heatmaps import TokenHeatmapGenerator
from benchmark.reporting.visualizations.ast_alignment import ASTAlignmentVisualizer
from benchmark.reporting.visualizations.causal_graphs import CausalGraphGenerator
from benchmark.reporting.visualizations.distributions import DistributionPlotter

__all__ = [
    # Legacy
    'JSONReportWriter',
    'HTMLReportWriter',
    'Leaderboard',
    'LeaderboardEntry',
    # Tiered reporting
    'ScientificReport',
    'OperationalReport',
    'ForensicReport',
    # Visualizations
    'TokenHeatmapGenerator',
    'ASTAlignmentVisualizer',
    'CausalGraphGenerator',
    'DistributionPlotter'
]
