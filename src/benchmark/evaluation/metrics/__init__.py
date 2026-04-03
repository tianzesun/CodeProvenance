"""Metrics module for classifier evaluation.

Provides extended evaluation metrics:
- ROC-AUC: Receiver Operating Characteristic - Area Under Curve
- Calibration error: Expected and Maximum calibration error
- Basic metrics: precision, recall, F1, accuracy
"""
from __future__ import annotations

from .roc_auc import (
    compute_roc_auc,
    compute_roc_curve,
    compute_average_precision,
)
from .calibration import (
    compute_calibration_error,
    compute_expected_calibration_error,
    compute_maximum_calibration_error,
    plot_calibration_curve,
)
from .basic import (
    precision,
    recall,
    f1_score,
    accuracy,
    compute_confusion_matrix,
    compute_metrics_from_confusion,
    compute_metrics,
    mean_average_precision,
    mean_reciprocal_rank,
    ndcg_at_k,
    top_k_precision,
)

__all__ = [
    # ROC-AUC
    "compute_roc_auc",
    "compute_roc_curve",
    "compute_average_precision",
    # Calibration
    "compute_calibration_error",
    "compute_expected_calibration_error",
    "compute_maximum_calibration_error",
    "plot_calibration_curve",
    # Basic metrics
    "precision",
    "recall",
    "f1_score",
    "accuracy",
    "compute_confusion_matrix",
    "compute_metrics_from_confusion",
    "compute_metrics",
    # Ranking metrics
    "mean_average_precision",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "top_k_precision",
]
