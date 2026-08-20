"""
EvalForge Statistical Evaluation Module
Production-grade statistical inference engine for benchmark systems.

Converts deterministic tool outputs into distributions, confidence intervals,
and robustness metrics under controlled perturbations.
"""

from .aggregation import ResultAggregator
from .ci_estimator import BootstrapCI
from .distribution_engine import DistributionEngine, ScoreDistribution
from .robustness import RobustnessScorer
from .sensitivity import SensitivityAnalyzer

__all__ = [
    "BootstrapCI",
    "DistributionEngine",
    "ResultAggregator",
    "RobustnessScorer",
    "ScoreDistribution",
    "SensitivityAnalyzer",
]
