"""Confidence interval computation for certification reports.

Provides multiple methods for computing confidence intervals:
- Bootstrap (gold standard for uncertainty estimation)
- Wilson score interval (recommended for binomial proportions)
- Clopper-Pearson (exact, conservative)
- Normal approximation (simple, not recommended for small samples)

References:
- Efron, B., & Tibshirani, R. J. (1993). An introduction to the bootstrap.
- Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for
  a binomial proportion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class ConfidenceInterval:
    """Confidence interval result.

    Attributes:
        point_estimate: Point estimate (e.g., observed proportion).
        ci_lower: Lower bound of confidence interval.
        ci_upper: Upper bound of confidence interval.
        confidence_level: Confidence level (e.g., 0.95 for 95%).
        method: Method used to compute the interval.
        n_samples: Number of samples used.
    """
    point_estimate: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    method: str
    n_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "point_estimate": self.point_estimate,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "confidence_level": self.confidence_level,
            "method": self.method,
            "n_samples": self.n_samples,
        }

    def width(self) -> float:
        """Compute the width of the confidence interval."""
        return self.ci_upper - self.ci_lower

    def contains(self, value: float) -> bool:
        """Check if a value is within the confidence interval."""
        return self.ci_lower <= value <= self.ci_upper

    def __str__(self) -> str:
        """Format as string."""
        return f"{self.point_estimate:.4f} [{self.ci_lower:.4f}, {self.ci_upper:.4f}]"


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


def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_bootstrap: int = 2000,
    confidence_level: float = 0.95,
    seed: int = 42,
    stratified: bool = True,
) -> BootstrapResult:
    """Compute bootstrap confidence interval for a metric.

    Bootstrap is the gold standard for uncertainty estimation in machine
    learning evaluation. It makes no assumptions about the distribution
    of the metric.

    Args:
        y_true: Ground truth labels.
        y_pred: Predicted labels or scores.
        metric_fn: Metric function that takes (y_true, y_pred) and returns a float.
        n_bootstrap: Number of bootstrap samples (default 2000).
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
    n_bootstrap: int = 2000,
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

    return np.array(indices)


def wilson_score_interval(
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute Wilson score confidence interval.

    The Wilson score interval is recommended for binomial proportions,
    especially for small samples or extreme proportions.

    Args:
        successes: Number of successes (e.g., correct predictions).
        trials: Total number of trials (e.g., total predictions).
        confidence_level: Confidence level (e.g., 0.95 for 95%).

    Returns:
        ConfidenceInterval with Wilson score interval.
    """
    if trials == 0:
        return ConfidenceInterval(
            point_estimate=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            confidence_level=confidence_level,
            method="wilson",
            n_samples=0,
        )

    p_hat = successes / trials
    z = stats.norm.ppf(1 - (1 - confidence_level) / 2)

    denominator = 1 + z**2 / trials
    center = (p_hat + z**2 / (2 * trials)) / denominator
    spread = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials) / denominator

    ci_lower = max(0.0, center - spread)
    ci_upper = min(1.0, center + spread)

    return ConfidenceInterval(
        point_estimate=p_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        confidence_level=confidence_level,
        method="wilson",
        n_samples=trials,
    )


def clopper_pearson_interval(
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute Clopper-Pearson (exact) confidence interval.

    The Clopper-Pearson interval is the exact interval based on the
    binomial distribution. It's conservative (guarantees coverage).

    Args:
        successes: Number of successes.
        trials: Total number of trials.
        confidence_level: Confidence level.

    Returns:
        ConfidenceInterval with Clopper-Pearson interval.
    """
    if trials == 0:
        return ConfidenceInterval(
            point_estimate=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            confidence_level=confidence_level,
            method="clopper_pearson",
            n_samples=0,
        )

    p_hat = successes / trials
    alpha = 1 - confidence_level

    # Use beta distribution for exact interval
    if successes == 0:
        ci_lower = 0.0
    else:
        ci_lower = stats.beta.ppf(alpha / 2, successes, trials - successes + 1)

    if successes == trials:
        ci_upper = 1.0
    else:
        ci_upper = stats.beta.ppf(1 - alpha / 2, successes + 1, trials - successes)

    return ConfidenceInterval(
        point_estimate=p_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        confidence_level=confidence_level,
        method="clopper_pearson",
        n_samples=trials,
    )


def normal_approximation_interval(
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Compute normal approximation confidence interval.

    Simple normal approximation (Wald interval). Not recommended for
    small samples or extreme proportions.

    Args:
        successes: Number of successes.
        trials: Total number of trials.
        confidence_level: Confidence level.

    Returns:
        ConfidenceInterval with normal approximation interval.
    """
    if trials == 0:
        return ConfidenceInterval(
            point_estimate=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            confidence_level=confidence_level,
            method="normal_approximation",
            n_samples=0,
        )

    p_hat = successes / trials
    z = stats.norm.ppf(1 - (1 - confidence_level) / 2)

    se = np.sqrt(p_hat * (1 - p_hat) / trials)

    ci_lower = max(0.0, p_hat - z * se)
    ci_upper = min(1.0, p_hat + z * se)

    return ConfidenceInterval(
        point_estimate=p_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        confidence_level=confidence_level,
        method="normal_approximation",
        n_samples=trials,
    )


def compute_confidence_interval(
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
    method: str = "wilson",
) -> ConfidenceInterval:
    """Compute confidence interval using specified method.

    Args:
        successes: Number of successes.
        trials: Total number of trials.
        confidence_level: Confidence level.
        method: Method to use ('wilson', 'clopper_pearson', 'normal').

    Returns:
        ConfidenceInterval.

    Raises:
        ValueError: If method is unknown.
    """
    if method == "wilson":
        return wilson_score_interval(successes, trials, confidence_level)
    elif method == "clopper_pearson":
        return clopper_pearson_interval(successes, trials, confidence_level)
    elif method == "normal":
        return normal_approximation_interval(successes, trials, confidence_level)
    else:
        raise ValueError(
            f"Unknown method: {method}. Use 'wilson', 'clopper_pearson', or 'normal'."
        )


def compute_all_confidence_intervals(
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> Dict[str, ConfidenceInterval]:
    """Compute confidence intervals using all available methods.

    Args:
        successes: Number of successes.
        trials: Total number of trials.
        confidence_level: Confidence level.

    Returns:
        Dictionary mapping method names to ConfidenceInterval results.
    """
    return {
        "wilson": wilson_score_interval(successes, trials, confidence_level),
        "clopper_pearson": clopper_pearson_interval(successes, trials, confidence_level),
        "normal": normal_approximation_interval(successes, trials, confidence_level),
    }


def compute_metric_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_bootstrap: int = 2000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> ConfidenceInterval:
    """Compute confidence interval for any metric using bootstrap.

    This is the recommended method for computing confidence intervals
    for arbitrary metrics.

    Args:
        y_true: Ground truth labels.
        y_pred: Predicted labels or scores.
        metric_fn: Metric function.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level.
        seed: Random seed.

    Returns:
        ConfidenceInterval with bootstrap CI.
    """
    result = bootstrap_ci(
        y_true, y_pred, metric_fn,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )

    return ConfidenceInterval(
        point_estimate=result.mean,
        ci_lower=result.ci_lower,
        ci_upper=result.ci_upper,
        confidence_level=confidence_level,
        method="bootstrap",
        n_samples=len(y_true),
    )