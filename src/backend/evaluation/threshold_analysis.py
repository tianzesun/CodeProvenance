"""Threshold Analysis and Calibration Tools.

Provides threshold sweep, metrics calculation, optimal threshold finding,
and precision-recall curve generation. All functionality is available
via both API and CLI interfaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class ThresholdMetrics(NamedTuple):
    """Classification metrics for a single threshold."""

    threshold: float
    precision: float
    recall: float
    f1_score: float
    true_positive_rate: float
    false_positive_rate: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "threshold": float(f"{self.threshold:.4f}"),
            "precision": float(f"{self.precision:.4f}"),
            "recall": float(f"{self.recall:.4f}"),
            "f1_score": float(f"{self.f1_score:.4f}"),
            "true_positive_rate": float(f"{self.true_positive_rate:.4f}"),
            "false_positive_rate": float(f"{self.false_positive_rate:.4f}"),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
        }


@dataclass
class ThresholdSweepResult:
    """Complete results from threshold sweep analysis."""

    thresholds: List[float]
    metrics: List[ThresholdMetrics]
    optimal_threshold: float
    optimal_metrics: ThresholdMetrics
    auc_pr: float
    total_samples: int
    positive_count: int
    negative_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "thresholds": [float(f"{t:.4f}") for t in self.thresholds],
            "metrics": [m.to_dict() for m in self.metrics],
            "optimal_threshold": float(f"{self.optimal_threshold:.4f}"),
            "optimal_metrics": self.optimal_metrics.to_dict(),
            "auc_pr": float(f"{self.auc_pr:.4f}"),
            "total_samples": self.total_samples,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
        }

    def save_json(self, path: Path) -> None:
        """Save sweep results to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def save_pr_curve(self, path: Path, dpi: int = 120) -> None:
        """Save Precision-Recall curve plot."""
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib is required for curve plotting")

        plt.figure(figsize=(8, 6), dpi=dpi)

        precisions = [m.precision for m in self.metrics]
        recalls = [m.recall for m in self.metrics]

        plt.plot(
            recalls,
            precisions,
            linewidth=2,
            label=f"PR Curve (AUC = {self.auc_pr:.3f})",
        )
        plt.scatter(
            self.optimal_metrics.recall,
            self.optimal_metrics.precision,
            color="red",
            marker="*",
            s=150,
            zorder=5,
            label=f"Optimal (F1 = {self.optimal_metrics.f1_score:.3f} @ {self.optimal_threshold:.2f})",
        )

        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.title("Precision-Recall Curve")
        plt.xlim(0.0, 1.02)
        plt.ylim(0.0, 1.02)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()

        path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(path)
        plt.close()


def calculate_threshold_metrics(
    scores: Sequence[float],
    labels: Sequence[bool],
    threshold: float,
) -> ThresholdMetrics:
    """Calculate classification metrics for a single threshold.

    Args:
        scores: Predicted similarity scores in [0, 1]
        labels: Ground truth boolean labels (True = positive)
        threshold: Decision threshold to evaluate

    Returns:
        Calculated metrics for this threshold
    """
    scores_np = np.asarray(scores, dtype=np.float64)
    labels_np = np.asarray(labels, dtype=np.bool_)

    predictions = scores_np >= threshold

    tp = int(np.sum(predictions & labels_np))
    fp = int(np.sum(predictions & ~labels_np))
    tn = int(np.sum(~predictions & ~labels_np))
    fn = int(np.sum(~predictions & labels_np))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = (
        2 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    tpr = recall
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return ThresholdMetrics(
        threshold=threshold,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        true_positive_rate=tpr,
        false_positive_rate=fpr,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
    )


def threshold_sweep(
    scores: Sequence[float],
    labels: Sequence[bool],
    start: float = 0.60,
    end: float = 0.80,
    step: float = 0.01,
) -> ThresholdSweepResult:
    """Perform threshold sweep over specified range.

    Args:
        scores: Predicted similarity scores in [0, 1]
        labels: Ground truth boolean labels (True = positive)
        start: Starting threshold value (inclusive)
        end: Ending threshold value (inclusive)
        step: Step size between thresholds

    Returns:
        Complete sweep results including optimal threshold
    """
    scores_np = np.asarray(scores, dtype=np.float64)
    labels_np = np.asarray(labels, dtype=np.bool_)

    thresholds = np.arange(start, end + step, step).round(4)
    metrics_list = [
        calculate_threshold_metrics(scores_np, labels_np, t) for t in thresholds
    ]

    f1_scores = np.array([m.f1_score for m in metrics_list])
    optimal_idx = int(np.argmax(f1_scores))
    optimal_threshold = float(thresholds[optimal_idx])
    optimal_metrics = metrics_list[optimal_idx]

    sorted_indices = np.argsort(scores_np)[::-1]
    sorted_scores = scores_np[sorted_indices]
    sorted_labels = labels_np[sorted_indices]

    tp_cum = np.cumsum(sorted_labels)
    recall_cum = tp_cum / tp_cum[-1] if tp_cum[-1] > 0 else np.zeros_like(tp_cum)
    precision_cum = tp_cum / np.arange(1, len(tp_cum) + 1)

    recall_cum = np.concatenate([[0.0], recall_cum, [1.0]])
    precision_cum = np.concatenate([[1.0], precision_cum, [0.0]])

    for i in range(len(precision_cum) - 1, 0, -1):
        precision_cum[i - 1] = np.maximum(precision_cum[i - 1], precision_cum[i])

    auc_pr = float(np.trapz(precision_cum[::-1], recall_cum[::-1]))

    return ThresholdSweepResult(
        thresholds=thresholds.tolist(),
        metrics=metrics_list,
        optimal_threshold=optimal_threshold,
        optimal_metrics=optimal_metrics,
        auc_pr=auc_pr,
        total_samples=len(labels),
        positive_count=int(np.sum(labels_np)),
        negative_count=int(np.sum(~labels_np)),
    )


def find_optimal_threshold(
    scores: Sequence[float],
    labels: Sequence[bool],
    metric: str = "f1",
    start: float = 0.0,
    end: float = 1.0,
    step: float = 0.001,
) -> Tuple[float, ThresholdMetrics]:
    """Find threshold that maximizes specified metric.

    Args:
        scores: Predicted similarity scores in [0, 1]
        labels: Ground truth boolean labels (True = positive)
        metric: Metric to maximize: 'f1', 'precision', 'recall'
        start: Minimum threshold to consider
        end: Maximum threshold to consider
        step: Step size for search

    Returns:
        Optimal threshold value and corresponding metrics
    """
    thresholds = np.arange(start, end + step, step)
    best_value = -1.0
    best_threshold = 0.5
    best_metrics = None

    for t in thresholds:
        metrics = calculate_threshold_metrics(scores, labels, t)

        if metric == "f1":
            current = metrics.f1_score
        elif metric == "precision":
            current = metrics.precision
        elif metric == "recall":
            current = metrics.recall
        else:
            raise ValueError(f"Unknown optimization metric: {metric}")

        if current > best_value:
            best_value = current
            best_threshold = t
            best_metrics = metrics

    return best_threshold, best_metrics


def global_threshold_override(threshold: Optional[float] = None) -> float:
    """Get or set global runtime threshold configuration.

    Args:
        threshold: Optional new global threshold value to set.
            If None, returns current active threshold.

    Returns:
        Current active global threshold.
    """
    from src.backend.benchmark.pipeline.threshold_config import DEFAULT_CONFIG

    if not hasattr(global_threshold_override, "_active_threshold"):
        global_threshold_override._active_threshold = (
            DEFAULT_CONFIG.thresholds.global_threshold
        )

    if threshold is not None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be in [0, 1], got {threshold}")
        global_threshold_override._active_threshold = threshold

    return global_threshold_override._active_threshold
