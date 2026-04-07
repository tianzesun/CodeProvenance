"""Evaluation metrics for plagiarism detection.

Implements:
- Precision, Recall, F1
- ROC-AUC and PR-AUC
- Confidence intervals
- Robustness scoring
- Calibration error (ECE)
"""
from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

try:
    from sklearn.metrics import (
        roc_curve,
        roc_auc_score,
        precision_recall_curve,
        average_precision_score,
        confusion_matrix,
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class MetricResult:
    """Result of metric computation."""
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    ece: float
    best_threshold: float
    confusion_matrix: Tuple[int, int, int, int]
    per_clone_type: Dict[int, Dict[str, float]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "ece": round(self.ece, 4),
            "best_threshold": round(self.best_threshold, 4),
            "confusion_matrix": {
                "tn": self.confusion_matrix[0],
                "fp": self.confusion_matrix[1],
                "fn": self.confusion_matrix[2],
                "tp": self.confusion_matrix[3],
            },
            "per_clone_type": {
                str(k): {k2: round(v2, 4) for k2, v2 in v.items()}
                for k, v in self.per_clone_type.items()
            }
        }


def compute_metrics(scores: List[float], 
                   labels: List[int],
                   thresholds: Optional[List[float]] = None) -> MetricResult:
    """Compute all evaluation metrics for detector scores.
    
    Args:
        scores: List of similarity scores [0.0, 1.0]
        labels: List of ground truth labels (0-4, CloneType)
        thresholds: Optional list of thresholds to test
    
    Returns:
        MetricResult with all computed metrics
    """
    scores_arr = np.array(scores)
    labels_arr = np.array(labels)
    
    # Binary labels: >= 2 is positive (clone)
    binary_labels = (labels_arr >= 2).astype(int)
    
    if thresholds is None:
        thresholds = np.linspace(0.1, 0.9, 17)
    
    # Find best threshold by F1
    best_f1 = 0.0
    best_threshold = 0.5
    best_cm = (0, 0, 0, 0)
    
    for t in thresholds:
        preds = (scores_arr >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(binary_labels, preds, labels=[0, 1]).ravel()
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
            best_cm = (tn, fp, fn, tp)
    
    tn, fp, fn, tp = best_cm
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    # ROC-AUC and PR-AUC
    if SKLEARN_AVAILABLE and len(np.unique(binary_labels)) > 1:
        roc_auc = roc_auc_score(binary_labels, scores_arr)
        pr_auc = average_precision_score(binary_labels, scores_arr)
    else:
        roc_auc = 0.0
        pr_auc = 0.0
    
    # Expected Calibration Error (ECE)
    ece = compute_calibration_error(scores_arr, binary_labels)
    
    # Per clone type performance
    per_clone_type = {}
    for clone_type in range(5):  # C0-C4
        mask = labels_arr == clone_type
        if np.any(mask):
            type_scores = scores_arr[mask]
            mean_score = np.mean(type_scores)
            median_score = np.median(type_scores)
            per_clone_type[clone_type] = {
                "count": int(np.sum(mask)),
                "mean_score": mean_score,
                "median_score": median_score,
            }
    
    return MetricResult(
        precision=precision,
        recall=recall,
        f1=best_f1,
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        ece=ece,
        best_threshold=best_threshold,
        confusion_matrix=best_cm,
        per_clone_type=per_clone_type
    )


def compute_calibration_error(scores: np.ndarray, 
                             labels: np.ndarray,
                             n_bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE).
    
    ECE measures how well predicted probabilities match observed frequencies.
    """
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    
    for bin_idx in range(n_bins):
        bin_min = bin_boundaries[bin_idx]
        bin_max = bin_boundaries[bin_idx + 1]
        
        bin_mask = (scores >= bin_min) & (scores < bin_max)
        bin_count = np.sum(bin_mask)
        
        if bin_count > 0:
            bin_scores = scores[bin_mask]
            bin_labels = labels[bin_mask]
            
            avg_score = np.mean(bin_scores)
            avg_acc = np.mean(bin_labels)
            
            ece += (bin_count / len(scores)) * abs(avg_score - avg_acc)
    
    return float(ece)


def compute_robustness(scores_under_transforms: List[float]) -> float:
    """Compute robustness score under transformations.
    
    Robustness = 1 - normalized variance
    
    Args:
        scores_under_transforms: List of scores for same code pair under different transforms
    
    Returns:
        Robustness score [0.0, 1.0] where 1.0 is perfectly robust
    """
    if len(scores_under_transforms) <= 1:
        return 1.0
    
    variance = np.var(scores_under_transforms)
    
    # Normalize variance: 0 variance → 1.0 robustness, 0.25 variance → 0.0
    robustness = max(0.0, 1.0 - (variance * 4.0))
    
    return float(robustness)


def compute_confidence_interval(data: List[float], 
                                confidence: float = 0.95) -> Tuple[float, float]:
    """Compute confidence interval for a list of values."""
    try:
        from scipy import stats
        arr = np.array(data)
        mean = np.mean(arr)
        sem = stats.sem(arr)
        h = sem * stats.t.ppf((1 + confidence) / 2, len(arr)-1)
        return float(mean - h), float(mean + h)
    except ImportError:
        # Fallback: simple std-based interval
        mean = np.mean(data)
        std = np.std(data)
        return float(mean - 1.96 * std), float(mean + 1.96 * std)


def compute_icc(scores_matrix: np.ndarray) -> float:
    """Compute Intraclass Correlation Coefficient (ICC) for inter-rater agreement.
    
    Used to measure consistency between multiple detectors.
    
    Args:
        scores_matrix: Shape (n_pairs, n_detectors)
    
    Returns:
        ICC(2,1) score [0.0, 1.0]
    """
    n_pairs, n_detectors = scores_matrix.shape
    
    # Two-way random effects, absolute agreement, single rater/measurement
    # ICC(2,1)
    from scipy.stats import f_oneway
    
    # Sum of squares between pairs
    pair_means = np.mean(scores_matrix, axis=1)
    overall_mean = np.mean(scores_matrix)
    ss_between = n_detectors * np.sum((pair_means - overall_mean) ** 2)
    
    # Sum of squares within pairs
    ss_within = np.sum((scores_matrix - pair_means[:, np.newaxis]) ** 2)
    
    # Mean squares
    ms_between = ss_between / (n_pairs - 1)
    ms_within = ss_within / (n_pairs * (n_detectors - 1))
    
    # F-test
    f_stat = ms_between / ms_within
    
    # ICC calculation
    icc = (ms_between - ms_within) / (ms_between + (n_detectors - 1) * ms_within)
    
    return float(max(0.0, icc))