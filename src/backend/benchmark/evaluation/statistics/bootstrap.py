"""Bootstrap confidence intervals for classifier evaluation.

Provides non-parametric bootstrap methods for estimating confidence intervals
of performance metrics. Bootstrap is the gold standard for uncertainty estimation
in machine learning evaluation.

References:
- Efron, B., & Tibshirani, R. J. (1993). An introduction to the bootstrap.
- Dietterich, T. G. (1998). Approximate statistical tests for comparing
  supervised classification learning algorithms.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np


@dataclass(frozen=True)
class BootstrapResult:
    """Result of bootstrap confidence interval computation.
    
    Attributes:
        mean: Mean of the bootstrap distribution.
        std: Standard deviation of the bootstrap distribution.
        ci_lower: Lower bound of confidence interval.
        ci_upper: Upper bound of confidence interval.
        confidence_level: Confidence level (e.g., 0.95 for 95%).
        n_bootstrap: Number of bootstrap samples used.
        bootstrap_means: Array of bootstrap means (for diagnostics).
    """
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    n_bootstrap: int
    bootstrap_means: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mean": self.mean,
            "std": self.std,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "confidence_level": self.confidence_level,
            "n_bootstrap": self.n_bootstrap,
        }


def bootstrap_confidence_interval(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
    stratified: bool = True,
) -> BootstrapResult:
    """Compute bootstrap confidence interval for a metric.
    
    Args:
        y_true: Ground truth labels.
        y_pred: Predicted labels or scores.
        metric_fn: Metric function that takes (y_true, y_pred) and returns a float.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level (e.g., 0.95 for 95%).
        seed: Random seed for reproducibility.
        stratified: Whether to use stratified bootstrap (preserves class distribution).
        
    Returns:
        BootstrapResult with confidence interval.
    """
    rng = np.random.RandomState(seed)
    n_samples = len(y_true)
    
    bootstrap_scores = np.zeros(n_bootstrap)
    
    for i in range(n_bootstrap):
        if stratified:
            # Stratified bootstrap: sample separately from each class
            indices = _stratified_sample(y_true, rng)
        else:
            # Simple bootstrap: sample with replacement
            indices = rng.randint(0, n_samples, size=n_samples)
        
        y_true_boot = y_true[indices]
        y_pred_boot = y_pred[indices]
        
        bootstrap_scores[i] = metric_fn(y_true_boot, y_pred_boot)
    
    # Compute confidence interval using percentile method
    alpha = 1 - confidence_level
    ci_lower = np.percentile(bootstrap_scores, 100 * alpha / 2)
    ci_upper = np.percentile(bootstrap_scores, 100 * (1 - alpha / 2))
    
    return BootstrapResult(
        mean=float(np.mean(bootstrap_scores)),
        std=float(np.std(bootstrap_scores)),
        ci_lower=float(ci_lower),
        ci_upper=float(ci_upper),
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
        bootstrap_means=bootstrap_scores,
    )


def bootstrap_metric(
    scores: np.ndarray,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> BootstrapResult:
    """Compute bootstrap confidence interval for a pre-computed metric.
    
    Use this when you already have per-sample scores and want to estimate
    the confidence interval of the mean.
    
    Args:
        scores: Array of per-sample scores.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level (e.g., 0.95 for 95%).
        seed: Random seed for reproducibility.
        
    Returns:
        BootstrapResult with confidence interval.
    """
    rng = np.random.RandomState(seed)
    n_samples = len(scores)
    
    bootstrap_means = np.zeros(n_bootstrap)
    
    for i in range(n_bootstrap):
        indices = rng.randint(0, n_samples, size=n_samples)
        bootstrap_means[i] = np.mean(scores[indices])
    
    alpha = 1 - confidence_level
    ci_lower = np.percentile(bootstrap_means, 100 * alpha / 2)
    ci_upper = np.percentile(bootstrap_means, 100 * (1 - alpha / 2))
    
    return BootstrapResult(
        mean=float(np.mean(bootstrap_means)),
        std=float(np.std(bootstrap_means)),
        ci_lower=float(ci_lower),
        ci_upper=float(ci_upper),
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
        bootstrap_means=bootstrap_means,
    )


def paired_bootstrap_test(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Paired bootstrap test for comparing two classifiers.
    
    Tests whether classifier A is significantly different from classifier B
    using the paired bootstrap test (Dietterich, 1998).
    
    Args:
        y_true: Ground truth labels.
        y_pred_a: Predictions from classifier A.
        y_pred_b: Predictions from classifier B.
        metric_fn: Metric function that takes (y_true, y_pred) and returns a float.
        n_bootstrap: Number of bootstrap samples.
        seed: Random seed for reproducibility.
        
    Returns:
        Dictionary with test results:
        - p_value: Two-tailed p-value.
        - significant: Whether the difference is significant at alpha=0.05.
        - mean_diff: Mean difference in performance.
        - ci_lower: Lower bound of difference confidence interval.
        - ci_upper: Upper bound of difference confidence interval.
    """
    rng = np.random.RandomState(seed)
    n_samples = len(y_true)
    
    # Compute observed difference
    score_a = metric_fn(y_true, y_pred_a)
    score_b = metric_fn(y_true, y_pred_b)
    observed_diff = score_a - score_b
    
    # Bootstrap differences
    diff_count = 0
    bootstrap_diffs = np.zeros(n_bootstrap)
    
    for i in range(n_bootstrap):
        indices = rng.randint(0, n_samples, size=n_samples)
        
        y_true_boot = y_true[indices]
        y_pred_a_boot = y_pred_a[indices]
        y_pred_b_boot = y_pred_b[indices]
        
        score_a_boot = metric_fn(y_true_boot, y_pred_a_boot)
        score_b_boot = metric_fn(y_true_boot, y_pred_b_boot)
        
        diff = score_a_boot - score_b_boot
        bootstrap_diffs[i] = diff
        
        # Count how often we see a difference as extreme as observed
        if abs(diff) >= abs(observed_diff):
            diff_count += 1
    
    # Two-tailed p-value
    p_value = diff_count / n_bootstrap
    
    # Confidence interval for the difference
    ci_lower = np.percentile(bootstrap_diffs, 2.5)
    ci_upper = np.percentile(bootstrap_diffs, 97.5)
    
    return {
        "p_value": float(p_value),
        "significant": p_value < 0.05,
        "mean_diff": float(observed_diff),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "n_bootstrap": n_bootstrap,
        "score_a": float(score_a),
        "score_b": float(score_b),
    }


def _stratified_sample(
    y: np.ndarray,
    rng: np.random.RandomState,
) -> np.ndarray:
    """Perform stratified bootstrap sampling.
    
    Preserves the class distribution in each bootstrap sample.
    
    Args:
        y: Labels array.
        rng: Random state.
        
    Returns:
        Indices for bootstrap sample.
    """
    unique_classes = np.unique(y)
    indices = []
    
    for cls in unique_classes:
        cls_indices = np.where(y == cls)[0]
        n_cls = len(cls_indices)
        boot_indices = rng.choice(cls_indices, size=n_cls, replace=True)
        indices.extend(boot_indices)
    
    rng.shuffle(indices)
    return np.array(indices)


def compute_bootstrap_distribution(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> np.ndarray:
    """Compute the full bootstrap distribution for a metric.
    
    Useful for visualizing the uncertainty distribution.
    
    Args:
        y_true: Ground truth labels.
        y_pred: Predicted labels or scores.
        metric_fn: Metric function.
        n_bootstrap: Number of bootstrap samples.
        seed: Random seed.
        
    Returns:
        Array of bootstrap metric values.
    """
    rng = np.random.RandomState(seed)
    n_samples = len(y_true)
    
    bootstrap_scores = np.zeros(n_bootstrap)
    
    for i in range(n_bootstrap):
        indices = rng.randint(0, n_samples, size=n_samples)
        y_true_boot = y_true[indices]
        y_pred_boot = y_pred[indices]
        bootstrap_scores[i] = metric_fn(y_true_boot, y_pred_boot)
    
    return bootstrap_scores