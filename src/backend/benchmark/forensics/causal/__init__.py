"""Causal analysis module for code similarity detection.

Provides root cause attribution and improvement ranking:
- RootCauseAttributor: Analyzes why detectors fail
- CausalRankingEngine: Ranks improvements by expected impact
"""
from src.backend.benchmark.forensics.causal.attribution import (
    RootCause,
    RootCauseAttributor,
    RootCauseReport,
)
from src.backend.benchmark.forensics.causal.ranking import (
    CausalRankingEngine,
    CausalRankingReport,
    ImprovementCandidate,
)

__all__ = [
    # Ranking
    "CausalRankingEngine",
    "CausalRankingReport",
    "ImprovementCandidate",
    # Attribution
    "RootCauseAttributor",
    "RootCause",
    "RootCauseReport",
]