"""ROC-AUC and related metrics for classifier evaluation.

Provides ROC curve computation and Area Under the Curve (AUC) calculation
for evaluating classifier discrimination ability.

References:
- Fawcett, T. (2006). An introduction to ROC analysis.
- Davis, J., & Goadrich, M. (2006). The relationship between Precision-Recall
  and ROC curves.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics import roc_curve, auc, average_precision_score


@dataclass(frozen=True)
class ROCResult:
    """Result of ROC curve computation.
    
    Attributes:
        fpr: False positive rates.
        tpr: True positive rates.
        thresholds: Thresholds used.
        auc: Area under the ROC curve.
    """
    fpr: np.ndarray
    tpr: np.ndarray
    thresholds: np.ndarray
    auc: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fpr": self.fpr.tolist(),
            "tpr": self.tpr.tolist(),
            "thresholds": self.thresholds.tolist(),
            "auc": self.auc,
        }


def compute_roc_curve(
    y_true: np.ndarray,
    y_score: np.ndarray,
    pos_label: int = 1,
) -> ROCResult:
    """Compute ROC curve.
    
    Args:
        y_true: Ground truth labels.
        y_score: Predicted probabilities or scores.
        pos_label: Label of positive class.
        
    Returns:
        ROCResult with ROC curve data.
    """
    fpr, tpr, thresholds = roc_curve(
        y_true, y_score, pos_label=pos_label
    )
    roc_auc = auc(fpr, tpr)
    
    return ROCResult(
        fpr=fpr,
        tpr=tpr,
        thresholds=thresholds,
        auc=float(roc_auc),
    )


def compute_roc_auc(
    y_true: np.ndarray,
    y_score: np.ndarray,
    pos_label: int = 1,
) -> float:
    """Compute ROC AUC score.
    
    Args:
        y_true: Ground truth labels.
        y_score: Predicted probabilities or scores.
        pos_label: Label of positive class.
        
    Returns:
        ROC AUC score.
    """
    result = compute_roc_curve(y_true, y_score, pos_label)
    return result.auc


def compute_average_precision(
    y_true: np.ndarray,
    y_score: np.ndarray,
    pos_label: int = 1,
) -> float:
    """Compute Average Precision score.
    
    Average Precision summarizes a precision-recall curve as the weighted mean
    of precisions achieved at each threshold, with the increase in recall
    from the previous threshold used as the weight.
    
    Args:
        y_true: Ground truth labels.
        y_score: Predicted probabilities or scores.
        pos_label: Label of positive class.
        
    Returns:
        Average Precision score.
    """
    return float(average_precision_score(
        y_true, y_score, pos_label=pos_label
    ))