"""Auto-Tuner - Benchmark automatic parameter optimization system.

Search strategies: Grid, Random, Bayesian (SMBO-lite).
Objective: maximise F-beta (default beta=2, recall-heavy for plagiarism).
Supports per-engine thresholds and cross-engine weight optimization.
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SearchStrategy(str, Enum):
    GRID = "grid"
    RANDOM = "random"
    BAYESIAN = "bayesian"


@dataclass
class ParameterRange:
    """Search range for a tunable parameter."""
    param_name: str
    low: float
    high: float
    step: float = 0.01

    def values(self) -> List[float]:
        vals = []
        v = self.low
        while v <= self.high + 1e-9:
            vals.append(round(v, 6))
            v += self.step
        return vals

    def sample(self) -> float:
        return round(random.uniform(self.low, self.high), 6)


@dataclass
class TuningConfig:
    """Configuration for the auto-tuner."""
    strategy: SearchStrategy = SearchStrategy.BAYESIAN
    max_iterations: int = 50
    random_seed: Optional[int] = 42
    beta: float = 2.0
    cv_folds: int = 3
    patience: int = 10

    # Parameter ranges
    threshold_range: ParameterRange = field(
        default_factory=lambda: ParameterRange("threshold", 0.0, 1.0, 0.01)
    )
    weight_range: ParameterRange = field(
        default_factory=lambda: ParameterRange("weight", 0.0, 3.0, 0.1)
    )


@dataclass
class TrialResult:
    """Result of a single parameter trial."""
    params: Dict[str, Any]
    score: float
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    fbeta: float = 0.0
    fold: int = -1


@dataclass
class TuningResult:
    """Final tuning result with best parameters."""
    best_params: Dict[str, Any]
    best_score: float
    best_precision: float = 0.0
    best_recall: float = 0.0
    best_f1: float = 0.0
    best_fbeta: float = 0.0
    all_trials: List[TrialResult] = field(default_factory=list)
    search_history: List[Dict[str, Any]] = field(default_factory=list)
    n_iterations: int = 0
    conver