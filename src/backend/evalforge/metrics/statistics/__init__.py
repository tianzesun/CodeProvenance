"""
EvalForge Statistical Evaluation Module
Production-grade statistical inference engine for benchmark systems.

Converts deterministic tool outputs into distributions, confidence intervals,
and robustness metrics under controlled perturbations.
"""

from .distribution_engine import DistributionEngine, ScoreDistribution
from .ci_estimator import BootstrapCI
from .robustness import RobustnessScorer
from .sensitivity import SensitivityAnalyzer
from .aggregation import ResultAggregator

__all__ = [
    "DistributionEngine",
    "ScoreDistribution",
    "BootstrapCI",
    "RobustnessScorer",
    "SensitivityAnalyzer",
    "ResultAggregator",
]