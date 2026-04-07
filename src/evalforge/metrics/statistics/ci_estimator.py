"""
Bootstrap Confidence Interval Estimator.

Computes statistically valid confidence intervals for non-Gaussian, bounded
score distributions. Uses resampling with replacement to avoid parametric
assumptions.
"""

from typing import List, Dict
import numpy as np


class BootstrapCI:
    """
    Bootstrap confidence interval calculator for similarity score distributions.
    
    Uses resampling with replacement to estimate confidence intervals without
    assuming normality, which is critical for bounded [0,1] similarity scores
    which are almost always skewed.
    """

    @staticmethod
    def compute(
        samples: List[float],
        alpha: float = 0.05,
        num_bootstraps: int = 2000
    ) -> Dict[str, float]:
        """
        Compute bootstrap confidence interval for distribution mean.

        Args:
            samples: List of sample scores
            alpha: Significance level (0.05 = 95% confidence)
            num_bootstraps: Number of bootstrap resamples

        Returns:
            Dictionary with ci_lower, ci_upper, and mean
        """
        sample_array = np.array(samples, dtype=np.float64)
        n = len(sample_array)

        bootstrap_means = np.empty(num_bootstraps, dtype=np.float64)

        for i in range(num_bootstraps):
            resample = np.random.choice(sample_array, size=n, replace=True)
            bootstrap_means[i] = np.mean(resample)

        lower_percentile = 100 * (alpha / 2)
        upper_percentile = 100 * (1 - alpha / 2)

        return {
            "ci_lower": float(np.percentile(bootstrap_means, lower_percentile)),
            "ci_upper": float(np.percentile(bootstrap_means, upper_percentile)),
            "mean": float(np.mean(sample_array))
        }

    @staticmethod
    def compute_batch(
        distributions: List[List[float]],
        alpha: float = 0.05,
        num_bootstraps: int = 2000
    ) -> List[Dict[str, float]]:
        """Compute confidence intervals for multiple distributions."""
        return [
            BootstrapCI.compute(dist, alpha, num_bootstraps)
            for dist in distributions
        ]