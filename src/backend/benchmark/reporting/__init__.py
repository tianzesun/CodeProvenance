"""Benchmark reporting module.

Provides tiered reporting (scientific, operational, forensic) and visualization
capabilities for benchmark results.
"""
from src.backend.benchmark.reporting.json_writer import JSONReportWriter
from src.backend.benchmark.reporting.html_report import HTMLReportWriter
from src.backend.benchmark.reporting.leaderboard import Leaderboard, LeaderboardEntry

# Tiered reporting
from src.backend.benchmark.reporting.tiers.scientific import ScientificReport
from src.backend.benchmark.reporting.tiers.operational import OperationalReport
from src.backend.benchmark.reporting.tiers.forensic import ForensicReport

# Visualizations
from src.backend.benchmark.reporting.visualizations.heatmaps import TokenHeatmapGenerator
from src.backend.benchmark.reporting.visualizations.ast_alignment import ASTAlignmentVisualizer
from src.backend.benchmark.reporting.visualizations.causal_graphs import CausalGraphGenerator
from src.backend.benchmark.reporting.visualizations.distributions import DistributionPlotter

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
