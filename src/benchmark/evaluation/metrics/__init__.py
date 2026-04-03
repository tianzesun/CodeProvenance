"""Metrics module for classifier evaluation.

Provides extended evaluation metrics:
- ROC-AUC: Receiver Operating Characteristic - Area Under Curve
- Calibration error: Expected and Maximum calibration error
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
]