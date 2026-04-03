"""Calibration metrics for classifier evaluation.

Provides metrics to evaluate how well-calibrated a classifier's
probability estimates are. A well-calibrated classifier should output
probabilities that match the true frequency of the positive class.

References:
- Niculescu-Mizil, A., & Caruana, R. (2005). Predicting good probabilities
  with supervised learning.
- Guo, C., et al. (2017). On calibration of modern neural networks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class CalibrationResult:
    """Result of calibration analysis.
    
    Attributes:
        ece: Expected Calibration Error.
        mce: Maximum Calibration Error.
        bin_accuracies: Accuracy per bin.
        bin_confidences: Mean confidence per bin.
        bin_counts: Number of samples per bin.
    """
    ece: float
    mce: float
    bin_accuracies: np.ndarray
    bin_confidences: np.ndarray
    bin_counts: np.ndarray
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ece": self.ece,
            "mce": self.mce,
            "bin_accuracies": self.bin_accuracies.tolist(),
            "bin_confidences": self.bin_confidences.tolist(),
            "bin_counts": self.bin_counts.tolist(),
        }


def compute_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
    strategy: str = "uniform",
) -> CalibrationResult:
    """Compute calibration error metrics.
    
    Args:
        y_true: Ground truth labels.
        y_prob: Predicted probabilities for positive class.
        n_bins: Number of bins for calibration.
        strategy: Binning strategy ('uniform' or 'quantile').
        
    Returns:
        CalibrationResult with calibration metrics.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    
    # Clip probabilities to [0, 1]
    y_prob = np.clip(y_prob, 0.0, 1.0)
    
    # Create bins
    if strategy == "uniform":
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    elif strategy == "quantile":
        bin_edges = np.percentile(y_prob, np.linspace(0, 100, n_bins + 1))
        bin_edges[0] = 0.0
        bin_edges[-1] = 1.0
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    # Compute bin statistics
    bin_accuracies = np.zeros(n_bins)
    bin_confidences = np.zeros(n_bins)
    bin_counts = np.zeros(n_bins)
    
    for i in range(n_bins):
        mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        if i == n_bins - 1:
            # Include right edge for last bin
            mask = (y_prob >= bin_edges[i]) & (y_prob <= bin_edges[i + 1])
        
        bin_count = np.sum(mask)
        bin_counts[i] = bin_count
        
        if bin_count > 0:
            bin_accuracies[i] = np.mean(y_true[mask])
            bin_confidences[i] = np.mean(y_prob[mask])
        else:
            bin_accuracies[i] = 0.0
            bin_confidences[i] = 0.0
    
    # Compute ECE and MCE
    total_samples = np.sum(bin_counts)
    if total_samples > 0:
        ece = np.sum(
            (bin_counts / total_samples) * np.abs(bin_accuracies - bin_confidences)
        )
        mce = np.max(np.abs(bin_accuracies - bin_confidences))
    else:
        ece = 0.0
        mce = 0.0
    
    return CalibrationResult(
        ece=float(ece),
        mce=float(mce),
        bin_accuracies=bin_accuracies,
        bin_confidences=bin_confidences,
        bin_counts=bin_counts,
    )


def compute_expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE).
    
    ECE is the weighted average of the absolute difference between
    accuracy and confidence across all bins.
    
    Args:
        y_true: Ground truth labels.
        y_prob: Predicted probabilities.
        n_bins: Number of bins.
        
    Returns:
        ECE value.
    """
    result = compute_calibration_error(y_true, y_prob, n_bins)
    return result.ece


def compute_maximum_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Maximum Calibration Error (MCE).
    
    MCE is the maximum absolute difference between accuracy and
    confidence across all bins.
    
    Args:
        y_true: Ground truth labels.
        y_prob: Predicted probabilities.
        n_bins: Number of bins.
        
    Returns:
        MCE value.
    """
    result = compute_calibration_error(y_true, y_prob, n_bins)
    return result.mce


def plot_calibration_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
    ax: Optional[Any] = None,
) -> Tuple[Any, CalibrationResult]:
    """Plot calibration curve (reliability diagram).
    
    Args:
        y_true: Ground truth labels.
        y_prob: Predicted probabilities.
        n_bins: Number of bins.
        ax: Matplotlib axes (optional).
        
    Returns:
        Tuple of (axes, CalibrationResult).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib is required for plotting calibration curves")
    
    result = compute_calibration_error(y_true, y_prob, n_bins)
    
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
    
    # Plot calibration curve
    ax.plot(
        result.bin_confidences,
        result.bin_accuracies,
        "s-",
        label="Calibration curve",
    )
    
    # Plot perfect calibration line
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Perfect calibration")
    
    # Add histogram of predictions
    ax2 = ax.twinx()
    ax2.hist(
        y_prob,
        bins=n_bins,
        alpha=0.3,
        color="gray",
        label="Prediction distribution",
    )
    ax2.set_ylabel("Count")
    
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title(f"Calibration Curve (ECE={result.ece:.4f}, MCE={result.mce:.4f})")
    ax.legend(loc="upper left")
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    
    return ax, result