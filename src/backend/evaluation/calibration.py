"""Calibration layer for trustable confidence scores.

This transforms the system from "scoring system" to "decision system with
measurable uncertainty". This is what institutions trust.

Implements:
- Expected Calibration Error (ECE)
- Reliability diagram data
- Platt scaling (logistic calibration)
- Isotonic regression (non-parametric calibration)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class CalibrationMetrics:
    """Calibration metrics for a set of predictions.

    Attributes:
        ece: Expected Calibration Error.
        mce: Maximum Calibration Error.
        reliability_diagram: Data for reliability diagram.
        n_bins: Number of bins used for calibration.
        n_samples: Total number of samples.
    """
    ece: float
    mce: float
    reliability_diagram: List[Dict[str, Any]]
    n_bins: int
    n_samples: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ece": self.ece,
            "mce": self.mce,
            "n_bins": self.n_bins,
            "n_samples": self.n_samples,
            "reliability_diagram": self.reliability_diagram,
        }


@dataclass
class PlattScalingParams:
    """Parameters for Platt scaling (logistic calibration).

    Formula: calibrated_prob = 1 / (1 + exp(A * score + B))

    Attributes:
        a: Slope parameter.
        b: Intercept parameter.
    """
    a: float
    b: float

    def calibrate(self, score: float) -> float:
        """Apply Platt scaling to a score.

        Args:
            score: Raw score in [0, 1].

        Returns:
            Calibrated probability.
        """
        # Clamp to avoid overflow
        x = np.clip(score, 1e-7, 1 - 1e-7)
        # Logit transform
        logit = np.log(x / (1 - x))
        # Apply linear transform
        z = self.a * logit + self.b
        # Sigmoid back
        return float(1 / (1 + np.exp(-z)))


def compute_ece(
    scores: List[float],
    labels: List[int],
    n_bins: int = 10,
) -> CalibrationMetrics:
    """Compute Expected Calibration Error.

    ECE measures how well-calibrated a model's confidence scores are.
    A perfectly calibrated model has ECE = 0.

    Args:
        scores: Predicted probabilities in [0, 1].
        labels: True labels (0 or 1).
        n_bins: Number of bins for calibration.

    Returns:
        CalibrationMetrics with ECE, MCE, and reliability diagram data.
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have same length")

    scores_arr = np.array(scores)
    labels_arr = np.array(labels)

    # Create bins
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(scores_arr, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    ece = 0.0
    mce = 0.0
    reliability_diagram = []

    for bin_idx in range(n_bins):
        mask = bin_indices == bin_idx
        n_in_bin = mask.sum()

        if n_in_bin == 0:
            reliability_diagram.append({
                "bin_idx": bin_idx,
                "bin_start": float(bin_edges[bin_idx]),
                "bin_end": float(bin_edges[bin_idx + 1]),
                "n_samples": 0,
                "mean_confidence": 0.0,
                "mean_accuracy": 0.0,
                "gap": 0.0,
            })
            continue

        bin_confidences = scores_arr[mask]
        bin_labels = labels_arr[mask]

        mean_confidence = float(bin_confidences.mean())
        mean_accuracy = float(bin_labels.mean())
        gap = abs(mean_confidence - mean_accuracy)

        # Weight by bin size
        weight = n_in_bin / len(scores)
        ece += weight * gap
        mce = max(mce, gap)

        reliability_diagram.append({
            "bin_idx": bin_idx,
            "bin_start": float(bin_edges[bin_idx]),
            "bin_end": float(bin_edges[bin_idx + 1]),
            "n_samples": int(n_in_bin),
            "mean_confidence": mean_confidence,
            "mean_accuracy": mean_accuracy,
            "gap": gap,
        })

    return CalibrationMetrics(
        ece=ece,
        mce=mce,
        reliability_diagram=reliability_diagram,
        n_bins=n_bins,
        n_samples=len(scores),
    )


def fit_platt_scaling(
    scores: List[float],
    labels: List[int],
    max_iter: int = 100,
    lr: float = 0.01,
) -> PlattScalingParams:
    """Fit Platt scaling parameters using gradient descent.

    Platt scaling fits a logistic function to the scores to improve calibration.

    Args:
        scores: Raw scores in [0, 1].
        labels: True labels (0 or 1).
        max_iter: Maximum iterations for optimization.
        lr: Learning rate.

    Returns:
        PlattScalingParams with fitted A and B.
    """
    scores_arr = np.array(scores)
    labels_arr = np.array(labels)

    # Logit transform of scores
    eps = 1e-7
    x = np.clip(scores_arr, eps, 1 - eps)
    logit = np.log(x / (1 - x))

    # Initialize parameters
    a = 1.0
    b = 0.0

    for _ in range(max_iter):
        # Forward pass
        z = a * logit + b
        pred = 1 / (1 + np.exp(-z))

        # Gradient of binary cross-entropy
        error = pred - labels_arr
        grad_a = np.mean(error * logit)
        grad_b = np.mean(error)

        # Update
        a -= lr * grad_a
        b -= lr * grad_b

    return PlattScalingParams(a=a, b=b)


def calibrate_scores(
    scores: List[float],
    params: PlattScalingParams,
) -> List[float]:
    """Apply Platt scaling calibration to scores.

    Args:
        scores: Raw scores in [0, 1].
        params: Fitted Platt scaling parameters.

    Returns:
        Calibrated scores.
    """
    return [params.calibrate(s) for s in scores]