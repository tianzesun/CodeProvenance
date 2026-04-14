"""Confidence interval methods for classifier evaluation.

Provides various methods for computing confidence intervals for proportions
(binomial confidence intervals), which are commonly used in classifier evaluation.

References:
- Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for
  a binomial proportion.
- Wilson, E. B. (1927). Probable inference, the law of succession, and
  statistical inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

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
    """
    point_estimate: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    method: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "point_estimate": self.point_estimate,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "confidence_level": self.confidence_level,
            "method": self.method,
        }
    
    def width(self) -> float:
        """Compute the width of the confidence interval."""
        return self.ci_upper - self.ci_lower
    
    def contains(self, value: float) -> bool:
        """Check if a value is within the confidence interval."""
        return self.ci_lower <= value <= self.ci_upper


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
    """
    if method == "wilson":
        return wilson_score_interval(successes, trials, confidence_level)
    elif method == "clopper_pearson":
        return clopper_pearson_interval(successes, trials, confidence_level)
    elif method == "normal":
        return normal_approximation_interval(successes, trials, confidence_level)
    else:
        raise ValueError(f"Unknown method: {method}. Use 'wilson', 'clopper_pearson', or 'normal'.")