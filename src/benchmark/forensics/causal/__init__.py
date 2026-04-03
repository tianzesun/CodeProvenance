"""Causal analysis module for code similarity detection.

Provides root cause attribution and improvement ranking:
- RootCauseAttributor: Analyzes why detectors fail
- CausalRankingEngine: Ranks improvements by expected impact
"""
from benchmark.forensics.causal.ranking import (
    CausalRankingEngine,
    CausalRankingReport,
    ImprovementCandidate,
)
from benchmark.forensics.causal.attribution import (
    RootCauseAttributor,
    RootCause,
    RootCauseReport,
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