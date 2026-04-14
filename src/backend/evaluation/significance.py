"""Statistical significance testing for benchmark results.

Provides:
- Bootstrap confidence intervals for F1, Precision, Recall
- McNemar's test for paired model comparison
- Effect size calculation (Cohen's d)

Usage:
    from benchmark.metrics.significance import (
        bootstrap_confidence_interval,
        mcnemar_test,
        compare_engines
    )
    
    # Bootstrap CI for a metric
    ci = bootstrap_confidence_interval(scores, labels, n_bootstrap=1000)
    
    # McNemar's test (paired comparison)
    result = mcnemar_test(y_true, y_pred_a, y_pred_b)
    
    # Compare two engines on the same dataset
    result = compare_engines(score_a, score_b, labels)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Bootstrap Confidence Intervals
# =============================================================================


def _compute_precision(tp: int, fp: int) -> float:
    return tp / (tp + fp) if (tp + fp) > 0 else 0.0


def _compute_recall(tp: int, fn: int) -> float:
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def _compute_f1(tp: int, fp: int, fn: int) -> float:
    prec = _compute_precision(tp, fp)
    rec = _compute_recall(tp, fn)
    return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0


def _bootstrap_metrics(
    scores: List[float],
    labels: List[int],
    threshold: float = 0.5,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """Compute bootstrap confidence intervals for classification metrics.
    
    Args:
        scores: Model similarity scores.
        labels: Ground truth labels (0 or 1).
        threshold: Classification threshold.
        n_bootstrap: Number of bootstrap samples.
        ci_level: Confidence interval level (e.g., 0.95).
        seed: Random seed for reproducibility.
        
    Returns:
        Dict with keys 'precision', 'recall', 'f1', each containing:
        - 'value': Point estimate
        - 'ci_lower': Lower confidence bound
        - 'ci_upper': Upper confidence bound
    """
    rng = random.Random(seed)
    n = len(scores)
    if n == 0:
        return {
            "precision": {"value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0},
            "recall": {"value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0},
            "f1": {"value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0},
        }
    
    # Compute point estimate
    tp_total = sum(1 for s, l in zip(scores, labels) if s >= threshold and l == 1)
    fp_total = sum(1 for s, l in zip(scores, labels) if s >= threshold and l == 0)
    fn_total = sum(1 for s, l in zip(scores, labels) if s < threshold and l == 1)
    
    point_f1 = _compute_f1(tp_total, fp_total, fn_total)
    point_prec = _compute_precision(tp_total, fp_total)
    point_rec = _compute_recall(tp_total, fn_total)
    
    # Bootstrap sampling
    boot_f1s: List[float] = []
    boot_precs: List[float] = []
    boot_recs: List[float] = []
    
    indices = list(range(n))
    for _ in range(n_bootstrap):
        sample_idx = [rng.choice(indices) for _ in range(n)]
        tp = sum(1 for i in sample_idx if scores[i] >= threshold and labels[i] == 1)
        fp = sum(1 for i in sample_idx if scores[i] >= threshold and labels[i] == 0)
        fn = sum(1 for i in sample_idx if scores[i] < threshold and labels[i] == 1)
        
        boot_f1s.append(_compute_f1(tp, fp, fn))
        boot_precs.append(_compute_precision(tp, fp))
        boot_recs.append(_compute_recall(tp, fn))
    
    # Compute CI bounds
    alpha = 1.0 - ci_level
    lower_pct = alpha / 2 * 100
    upper_pct = (1.0 - alpha / 2) * 100
    
    def percentile(data: List[float], pct: float) -> float:
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (pct / 100.0)
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_data) else f
        d = k - f
        return sorted_data[f] * (1 - d) + sorted_data[c] * d
    
    return {
        "f1": {
            "value": round(point_f1, 4),
            "ci_lower": round(percentile(boot_f1s, lower_pct), 4),
            "ci_upper": round(percentile(boot_f1s, upper_pct), 4),
        },
        "precision": {
            "value": round(point_prec, 4),
            "ci_lower": round(percentile(boot_precs, lower_pct), 4),
            "ci_upper": round(percentile(boot_precs, upper_pct), 4),
        },
        "recall": {
            "value": round(point_rec, 4),
            "ci_lower": round(percentile(boot_recs, lower_pct), 4),
            "ci_upper": round(percentile(boot_recs, upper_pct), 4),
        },
    }


def bootstrap_confidence_interval(
    scores: List[float],
    labels: List[int],
    threshold: float = 0.5,
    ci_level: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """Public API: Compute bootstrap confidence intervals for F1/P/R.
    
    Args:
        scores: Model similarity scores [0, 1].
        labels: Ground truth binary labels.
        threshold: Decision threshold for classification.
        ci_level: Confidence level (default 0.95).
        n_bootstrap: Number of bootstrap resamples (default 1000).
        seed: Random seed for reproducibility.
        
    Returns:
        Dict with 'f1', 'precision', 'recall' each containing:
        'value' (point estimate), 'ci_lower', 'ci_upper'.
        
    Example:
        >>> ci = bootstrap_confidence_interval(scores, labels)
        >>> print(f"F1={ci['f1']['value']:.2%} [{ci['f1']['ci_lower']:.2%}, {ci['f1']['ci_upper']:.2%}]")
    """
    return _bootstrap_metrics(scores, labels, threshold, n_bootstrap, ci_level, seed)


# =============================================================================
# McNemar's Test for Paired Model Comparison
# =============================================================================


@dataclass
class McNemarResult:
    """Result of McNemar's test comparing two models."""
    chi_squared: float
    p_value: float
    n_disagree_a_correct: int  # Cases where A is right but B is wrong
    n_disagree_b_correct: int  # Cases where B is right but A is wrong
    is_significant: bool  # Whether difference is statistically significant
    significance_threshold: float = 0.05


def mcnemar_test(
    y_true: List[int],
    y_pred_a: List[int],
    y_pred_b: List[int],
    significance_level: float = 0.05,
    continuity_correction: bool = True,
) -> McNemarResult:
    """McNemar's test for paired comparison of two classifiers.
    
    Tests the null hypothesis that both models have the same error rate.
    A low p-value (< 0.05) suggests the models have different error rates.
    
    Args:
        y_true: Ground truth binary labels.
        y_pred_a: Predictions from model A (0 or 1).
        y_pred_b: Predictions from model B (0 or 1).
        significance_level: Alpha threshold for significance.
        continuity_correction: Use Edwards' continuity correction.
        
    Returns:
        McNemarResult with test statistics.
    """
    n = len(y_true)
    if n != len(y_pred_a) or n != len(y_pred_b):
        raise ValueError("All inputs must have same length")
    
    # Count discordant pairs
    n_01 = 0  # A wrong, B correct (relative to y_true)
    n_10 = 0  # A correct, B wrong
    
    for i in range(n):
        a_correct = (y_pred_a[i] == y_true[i])
        b_correct = (y_pred_b[i] == y_true[i])
        
        if not a_correct and b_correct:
            n_01 += 1
        elif a_correct and not b_correct:
            n_10 += 1
    
    # McNemar's chi-squared test
    discordant_sum = n_01 + n_10
    if discordant_sum == 0:
        return McNemarResult(
            chi_squared=0.0,
            p_value=1.0,
            n_disagree_a_correct=n_01,
            n_disagree_b_correct=n_10,
            is_significant=False,
            significance_threshold=significance_level,
        )
    
    if continuity_correction:
        # Edwards' correction: (|n_01 - n_10| - 1)^2 / (n_01 + n_10)
        chi_sq = (abs(n_01 - n_10) - 1.0) ** 2 / discordant_sum
    else:
        chi_sq = (n_01 - n_10) ** 2 / discordant_sum
    
    # Approximate p-value using chi-squared CDF with df=1
    p_value = _chi_square_p_value_1df(chi_sq)
    
    return McNemarResult(
        chi_squared=round(chi_sq, 4),
        p_value=round(p_value, 4),
        n_disagree_a_correct=n_01,
        n_disagree_b_correct=n_10,
        is_significant=p_value < significance_level,
        significance_threshold=significance_level,
    )


def _chi_square_p_value_1df(x: float) -> float:
    """Approximate p-value for chi-squared with 1 degree of freedom.
    
    Uses the relationship: P(χ² > x) = 2 * (1 - Φ(√x))
    where Φ is the standard normal CDF.
    """
    if x <= 0:
        return 1.0
    
    import math
    z = math.sqrt(x)
    
    # Approximation of 1 - Φ(z) using Abramowitz and Stegun
    # P(Z > z) ≈ ½ * (1 + erf(-z/√2))
    # Using complementary error function approximation
    p = 0.5 * _erfc(z / math.sqrt(2))
    
    return 2 * p


def _erfc(x: float) -> float:
    """Complementary error function approximation.
    
    Abramowitz and Stegun formula 7.1.26.
    """
    import math
    
    # Constants for approximation
    t = 1.0 / (1.0 + 0.5 * abs(x))
    
    tau = t * math.exp(-x * x 
        - 1.26551223
        + 1.00002368 * t
        + 0.37409196 * t * t
        + 0.09678418 * t * t * t
        - 0.18628806 * t * t * t * t
        + 0.27886807 * t * t * t * t * t
        - 1.13520398 * t * t * t * t * t * t
        + 1.48851587 * t * t * t * t * t * t * t
        - 0.82215223 * t * t * t * t * t * t * t * t
        + 0.17087277 * t * t * t * t * t * t * t * t * t)
    
    return tau if x >= 0 else 2.0 - tau


# =============================================================================
# Engine Comparison
# =============================================================================


@dataclass
class EngineComparisonResult:
    """Result of comparing two engines."""
    metric_name: str
    engine_a_value: float
    engine_b_value: float
    absolute_diff: float
    relative_diff_pct: float
    ci_a_lower: float
    ci_a_upper: float
    ci_b_lower: float
    ci_b_upper: float
    p_value: float
    is_significant: bool
    interpretation: str  # "A is significantly better", "No significant difference", etc.


def compare_engines(
    scores_a: List[float],
    scores_b: List[float],
    labels: List[int],
    metric: str = "f1",
    threshold: float = 0.5,
    ci_level: float = 0.95,
) -> EngineComparisonResult:
    """Compare two engines on the same dataset.
    
    Args:
        scores_a: Engine A similarity scores.
        scores_b: Engine B similarity scores.
        labels: Ground truth binary labels.
        metric: Metric to compare ('f1', 'precision', 'recall').
        threshold: Decision threshold.
        ci_level: Confidence interval level.
        
    Returns:
        EngineComparisonResult with full statistical analysis.
    """
    n = len(labels)
    
    # Compute bootstrap CIs for each engine
    ci_a = bootstrap_confidence_interval(scores_a, labels, threshold, ci_level)
    ci_b = bootstrap_confidence_interval(scores_b, labels, threshold, ci_level)
    
    # Binary predictions
    pred_a = [1 if s >= threshold else 0 for s in scores_a]
    pred_b = [1 if s >= threshold else 0 for s in scores_b]
    
    # McNemar's test
    mc = mcnemar_test(labels, pred_a, pred_b)
    
    # Get metric values
    value_a = ci_a[metric]["value"]
    value_b = ci_b[metric]["value"]
    
    abs_diff = abs(value_a - value_b)
    rel_diff = (abs_diff / max(value_a, value_b) * 100) if max(value_a, value_b) > 0 else 0.0
    
    # Determine winner
    better_a = value_a > value_b
    if mc.is_significant:
        interpretation = (
            f"Engine A is significantly better ({metric}: {value_a:.4f} vs {value_b:.4f}, "
            f"p={mc.p_value:.4f})" if better_a else
            f"Engine B is significantly better ({metric}: {value_b:.4f} vs {value_a:.4f}, "
            f"p={mc.p_value:.4f})"
        )
    else:
        # Check if CI overlap
        overlap = not (ci_a[metric]["ci_lower"] > ci_b[metric]["ci_upper"] or
                       ci_b[metric]["ci_lower"] > ci_a[metric]["ci_upper"])
        interpretation = (
            f"No significant difference ({metric}: {value_a:.4f} vs {value_b:.4f}, "
            f"p={mc.p_value:.4f}, CI {'overlap' if overlap else 'do not overlap'})"
        )
    
    return EngineComparisonResult(
        metric_name=metric,
        engine_a_value=value_a,
        engine_b_value=value_b,
        absolute_diff=round(abs_diff, 4),
        relative_diff_pct=round(rel_diff, 2),
        ci_a_lower=ci_a[metric]["ci_lower"],
        ci_a_upper=ci_a[metric]["ci_upper"],
        ci_b_lower=ci_b[metric]["ci_lower"],
        ci_b_upper=ci_b[metric]["ci_upper"],
        p_value=mc.p_value,
        is_significant=mc.is_significant,
        interpretation=interpretation,
    )


# =============================================================================
# Convenience function for integration with Layer 1
# =============================================================================


def add_significance_to_results(
    scores: List[float],
    labels: List[int],
    threshold: float = 0.5,
    ci_level: float = 0.95,
    n_bootstrap: int = 1000,
) -> Dict[str, Any]:
    """Compute metrics with bootstrap confidence intervals.
    
    Args:
        scores: Similarity scores.
        labels: Ground truth labels.
        threshold: Decision threshold.
        ci_level: Confidence level.
        n_bootstrap: Bootstrap resamples.
        
    Returns:
        Dict with point estimates and confidence intervals for each metric.
    """
    ci = bootstrap_confidence_interval(scores, labels, threshold, ci_level, n_bootstrap)
    
    # Also compute per-class confusion matrix
    tp = sum(1 for s, l in zip(scores, labels) if s >= threshold and l == 1)
    fp = sum(1 for s, l in zip(scores, labels) if s >= threshold and l == 0)
    tn = sum(1 for s, l in zip(scores, labels) if s < threshold and l == 0)
    fn = sum(1 for s, l in zip(scores, labels) if s < threshold and l == 1)
    
    return {
        "threshold": threshold,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "f1": ci["f1"],
        "precision": ci["precision"],
        "recall": ci["recall"],
    }