"""Benchmark reporting module.

Provides tiered reporting (scientific, operational, forensic) and visualization
capabilities for benchmark results.
"""
from src.benchmark.reporting.json_writer import JSONReportWriter
from src.benchmark.reporting.html_report import HTMLReportWriter
from src.benchmark.reporting.leaderboard import Leaderboard, LeaderboardEntry

# Tiered reporting
from src.benchmark.reporting.tiers.scientific import ScientificReport
from src.benchmark.reporting.tiers.operational import OperationalReport
from src.benchmark.reporting.tiers.forensic import ForensicReport

# Visualizations
from src.benchmark.reporting.visualizations.heatmaps import TokenHeatmapGenerator
from src.benchmark.reporting.visualizations.ast_alignment import ASTAlignmentVisualizer
from src.benchmark.reporting.visualizations.causal_graphs import CausalGraphGenerator
from src.benchmark.reporting.visualizations.distributions import DistributionPlotter

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
