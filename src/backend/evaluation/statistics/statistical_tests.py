from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, List, Tuple

import numpy as np


# =========================
# Data Structures
# =========================

@dataclass(frozen=True)
class ConfidenceInterval:
    lower: float
    upper: float
    mean: float
    std: float
    confidence: float


@dataclass(frozen=True)
class SignificanceResult:
    delta: float
    p_value: float
    significant: bool
    confidence: float


# =========================
# Utility Functions
# =========================

def _validate_scores(scores: List[float]) -> None:
    if not scores:
        raise ValueError("Scores list cannot be empty")
    for s in scores:
        if not (0.0 <= s <= 1.0):
            raise ValueError(f"Invalid score: {s}, must be in [0,1]")


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


# =========================
# Bootstrap Confidence Interval
# =========================

def bootstrap_confidence_interval(
    scores: List[float],
    num_samples: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> ConfidenceInterval:
    """
    Compute bootstrap confidence interval for a metric (e.g., F1 across pairs).
    """
    _validate_scores(scores)
    _set_seed(seed)

    scores_np = np.array(scores)
    n = len(scores_np)

    boot_means = []

    for _ in range(num_samples):
        sample = np.random.choice(scores_np, size=n, replace=True)
        boot_means.append(np.mean(sample))

    boot_means = np.array(boot_means)

    lower_q = (1 - confidence) / 2
    upper_q = 1 - lower_q

    lower = np.quantile(boot_means, lower_q)
    upper = np.quantile(boot_means, upper_q)

    return ConfidenceInterval(
        lower=float(lower),
        upper=float(upper),
        mean=float(np.mean(boot_means)),
        std=float(np.std(boot_means)),
        confidence=confidence,
    )


# =========================
# Paired Bootstrap Test
# =========================

def paired_bootstrap_test(
    scores_a: List[float],
    scores_b: List[float],
    num_samples: int = 1000,
    seed: int = 42,
    confidence: float = 0.95,
) -> SignificanceResult:
    """
    Paired bootstrap test for comparing two systems.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError("Score lists must have same length")

    _validate_scores(scores_a)
    _validate_scores(scores_b)
    _set_seed(seed)

    a = np.array(scores_a)
    b = np.array(scores_b)

    n = len(a)
    deltas = []

    for _ in range(num_samples):
        idx = np.random.choice(n, size=n, replace=True)
        delta = np.mean(a[idx] - b[idx])
        deltas.append(delta)

    deltas = np.array(deltas)

    observed_delta = float(np.mean(a - b))

    # Two-sided p-value
    p_value = float(np.mean(np.abs(deltas) >= abs(observed_delta)))

    return SignificanceResult(
        delta=observed_delta,
        p_value=p_value,
        significant=p_value < (1 - confidence),
        confidence=confidence,
    )


# =========================
# McNemar’s Test
# =========================

def mcnemar_test(
    y_true: List[int],
    y_pred_a: List[int],
    y_pred_b: List[int],
    continuity_correction: bool = True,
    alpha: float = 0.05,
) -> SignificanceResult:
    """
    McNemar's test for paired binary classification.
    """
    if not (len(y_true) == len(y_pred_a) == len(y_pred_b)):
        raise ValueError("All input lists must have same length")

    n01 = 0  # A wrong, B correct
    n10 = 0  # A correct, B wrong

    for yt, a, b in zip(y_true, y_pred_a, y_pred_b):
        correct_a = (a == yt)
        correct_b = (b == yt)

        if correct_a and not correct_b:
            n10 += 1
        elif not correct_a and correct_b:
            n01 += 1

    if n01 + n10 == 0:
        # Identical predictions
        return SignificanceResult(
            delta=0.0,
            p_value=1.0,
            significant=False,
            confidence=1 - alpha,
        )

    if continuity_correction:
        chi2 = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
    else:
        chi2 = (n01 - n10) ** 2 / (n01 + n10)

    # Approximate p-value from chi-square (df=1)
    p_value = math.exp(-0.5 * chi2)

    return SignificanceResult(
        delta=float(n10 - n01),
        p_value=p_value,
        significant=p_value < alpha,
        confidence=1 - alpha,
    )


# =========================
# Convenience API (Recommended)
# =========================

def compare_systems(
    scores_a: List[float],
    scores_b: List[float],
    y_true: List[int] | None = None,
    y_pred_a: List[int] | None = None,
    y_pred_b: List[int] | None = None,
) -> dict:
    """
    Unified comparison interface.
    """
    result = {
        "bootstrap": paired_bootstrap_test(scores_a, scores_b),
        "confidence_a": bootstrap_confidence_interval(scores_a),
        "confidence_b": bootstrap_confidence_interval(scores_b),
    }

    if y_true and y_pred_a and y_pred_b:
        result["mcnemar"] = mcnemar_test(y_true, y_pred_a, y_pred_b)

    return result
