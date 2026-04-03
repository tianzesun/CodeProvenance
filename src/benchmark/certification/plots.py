"""Plot generation for certification reports.

Generates publication-grade visualizations for:
- Reliability diagrams (calibration analysis)
- Degradation curves (performance vs obfuscation)
- ROC curves
- Score distributions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class ReliabilityDiagramPlotter:
    """Plotter for reliability diagrams (calibration analysis).

    A reliability diagram shows how well-calibrated a classifier is by plotting
    predicted probabilities against observed frequencies. This is rarely done
    by competitors and is a strong differentiator.
    """
    n_bins: int = 10
    title: str = "Reliability Diagram"

    def compute_calibration_data(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """Compute calibration data for plotting.

        Args:
            y_true: Ground truth binary labels.
            y_prob: Predicted probabilities.

        Returns:
            Dictionary with bin_centers, bin_accuracies, bin_counts.
        """
        bin_edges = np.linspace(0, 1, self.n_bins + 1)
        bin_indices = np.digitize(y_prob, bin_edges) - 1
        bin_indices = np.clip(bin_indices, 0, self.n_bins - 1)

        bin_centers = []
        bin_accuracies = []
        bin_counts = []

        for i in range(self.n_bins):
            mask = bin_indices == i
            count = np.sum(mask)
            if count > 0:
                bin_centers.append(np.mean(y_prob[mask]))
                bin_accuracies.append(np.mean(y_true[mask]))
                bin_counts.append(count)
            else:
                bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)
                bin_accuracies.append(0.0)
                bin_counts.append(0)

        return {
            "bin_centers": np.array(bin_centers),
            "bin_accuracies": np.array(bin_accuracies),
            "bin_counts": np.array(bin_counts),
        }

    def to_dict(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
    ) -> Dict[str, Any]:
        """Convert calibration data to dictionary for JSON export.

        Args:
            y_true: Ground truth labels.
            y_prob: Predicted probabilities.

        Returns:
            Dictionary with calibration data.
        """
        data = self.compute_calibration_data(y_true, y_prob)

        # Compute ECE
        ece = np.mean(np.abs(data["bin_accuracies"] - data["bin_centers"]))

        return {
            "title": self.title,
            "n_bins": self.n_bins,
            "bin_centers": data["bin_centers"].tolist(),
            "bin_accuracies": data["bin_accuracies"].tolist(),
            "bin_counts": data["bin_counts"].tolist(),
            "ece": float(ece),
        }


@dataclass
class DegradationCurvePlotter:
    """Plotter for degradation curves.

    Shows how performance degrades as:
    - Clone type increases (Type I → IV)
    - Difficulty increases (EASY → HARD → EXPERT)
    - Obfuscation level increases
    """
    title: str = "Performance Degradation"

    def compute_degradation_data(
        self,
        strata_values: List[float],
        f1_scores: List[float],
        stratum_name: str = "Stratum",
    ) -> Dict[str, Any]:
        """Compute degradation curve data.

        Args:
            strata_values: List of stratum values (x-axis).
            f1_scores: List of F1 scores (y-axis).
            stratum_name: Name of the stratum dimension.

        Returns:
            Dictionary with curve data.
        """
        if len(strata_values) != len(f1_scores):
            raise ValueError("strata_values and f1_scores must have same length")

        # Compute degradation
        if len(f1_scores) >= 2:
            degradation = f1_scores[0] - f1_scores[-1]
            degradation_pct = (degradation / f1_scores[0] * 100) if f1_scores[0] > 0 else 0.0
        else:
            degradation = 0.0
            degradation_pct = 0.0

        return {
            "title": self.title,
            "stratum_name": stratum_name,
            "strata_values": [float(v) for v in strata_values],
            "f1_scores": [float(s) for s in f1_scores],
            "degradation": float(degradation),
            "degradation_pct": float(degradation_pct),
        }

    def to_dict(
        self,
        clone_types: Optional[List[int]] = None,
        clone_f1_scores: Optional[List[float]] = None,
        difficulties: Optional[List[str]] = None,
        difficulty_f1_scores: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Convert degradation data to dictionary.

        Args:
            clone_types: List of clone types.
            clone_f1_scores: F1 scores by clone type.
            difficulties: List of difficulty levels.
            difficulty_f1_scores: F1 scores by difficulty.

        Returns:
            Dictionary with degradation data.
        """
        result: Dict[str, Any] = {"title": self.title}

        if clone_types and clone_f1_scores:
            result["clone_type"] = self.compute_degradation_data(
                [float(ct) for ct in clone_types],
                clone_f1_scores,
                "Clone Type",
            )

        if difficulties and difficulty_f1_scores:
            diff_map = {"EASY": 1.0, "HARD": 2.0, "EXPERT": 3.0}
            diff_values = [diff_map.get(d, 0.0) for d in difficulties]
            result["difficulty"] = self.compute_degradation_data(
                diff_values,
                difficulty_f1_scores,
                "Difficulty",
            )

        return result