"""Basic classification metrics for benchmark evaluation.

Provides standard precision, recall, F1, and accuracy metrics.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union
import numpy as np


def precision(tp: int, fp: int) -> float:
    """Compute precision: TP / (TP + FP).
    
    Args:
        tp: True positives.
        fp: False positives.
        
    Returns:
        Precision score (0.0 to 1.0).
    """
    if tp + fp == 0:
        return 0.0
    return tp / (tp + fp)


def recall(tp: int, fn: int) -> float:
    """Compute recall: TP / (TP + FN).
    
    Args:
        tp: True positives.
        fn: False negatives.
        
    Returns:
        Recall score (0.0 to 1.0).
    """
    if tp + fn == 0:
        return 0.0
    return tp / (tp + fn)


def f1_score(precision_val: float, recall_val: float) -> float:
    """Compute F1 score: 2 * precision * recall / (precision + recall).
    
    Args:
        precision_val: Precision score.
        recall_val: Recall score.
        
    Returns:
        F1 score (0.0 to 1.0).
    """
    if precision_val + recall_val == 0:
        return 0.0
    return 2 * precision_val * recall_val / (precision_val + recall_val)


def accuracy(tp: int, tn: int, fp: int, fn: int) -> float:
    """Compute accuracy: (TP + TN) / (TP + TN + FP + FN).
    
    Args:
        tp: True positives.
        tn: True negatives.
        fp: False positives.
        fn: False negatives.
        
    Returns:
        Accuracy score (0.0 to 1.0).
    """
    total = tp + tn + fp + fn
    if total == 0:
        return 0.0
    return (tp + tn) / total


def compute_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, int]:
    """Compute confusion matrix from binary labels.
    
    Args:
        y_true: Ground truth labels (0 or 1).
        y_pred: Predicted labels (0 or 1).
        
    Returns:
        Dictionary with tp, fp, tn, fn counts.
    """
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def compute_metrics_from_confusion(
    confusion: Dict[str, int],
) -> Dict[str, float]:
    """Compute all metrics from confusion matrix.
    
    Args:
        confusion: Dictionary with tp, fp, tn, fn.
        
    Returns:
        Dictionary with precision, recall, f1, accuracy.
    """
    tp = confusion["tp"]
    fp = confusion["fp"]
    tn = confusion["tn"]
    fn = confusion["fn"]
    
    prec = precision(tp, fp)
    rec = recall(tp, fn)
    f1 = f1_score(prec, rec)
    acc = accuracy(tp, tn, fp, fn)
    
    return {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "accuracy": acc,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Compute all classification metrics from binary labels.
    
    Args:
        y_true: Ground truth labels (0 or 1).
        y_pred: Predicted labels (0 or 1).
        
    Returns:
        Dictionary with all metrics.
    """
    confusion = compute_confusion_matrix(y_true, y_pred)
    return compute_metrics_from_confusion(confusion)


def mean_average_precision(
    y_true: np.ndarray,
    y_scores: np.ndarray,
) -> float:
    """Compute mean average precision for ranking evaluation.
    
    Args:
        y_true: Ground truth labels (0 or 1).
        y_scores: Predicted scores (higher = more relevant).
        
    Returns:
        Mean average precision score.
    """
    # Sort by scores in descending order
    sorted_indices = np.argsort(-y_scores)
    y_true_sorted = y_true[sorted_indices]
    
    # Compute precision at each position
    precisions = []
    num_relevant = 0
    
    for i, label in enumerate(y_true_sorted):
        if label == 1:
            num_relevant += 1
            precisions.append(num_relevant / (i + 1))
    
    if not precisions:
        return 0.0
    
    return float(np.mean(precisions))


def mean_reciprocal_rank(
    y_true: np.ndarray,
    y_scores: np.ndarray,
) -> float:
    """Compute mean reciprocal rank for ranking evaluation.
    
    Args:
        y_true: Ground truth labels (0 or 1).
        y_scores: Predicted scores (higher = more relevant).
        
    Returns:
        Mean reciprocal rank score.
    """
    # Sort by scores in descending order
    sorted_indices = np.argsort(-y_scores)
    y_true_sorted = y_true[sorted_indices]
    
    # Find rank of first relevant item
    for i, label in enumerate(y_true_sorted):
        if label == 1:
            return 1.0 / (i + 1)
    
    return 0.0


def ndcg_at_k(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    k: int = 10,
) -> float:
    """Compute normalized discounted cumulative gain at k.
    
    Args:
        y_true: Ground truth labels (0 or 1).
        y_scores: Predicted scores (higher = more relevant).
        k: Number of top results to consider.
        
    Returns:
        NDCG@k score.
    """
    # Sort by scores in descending order
    sorted_indices = np.argsort(-y_scores)
    y_true_sorted = y_true[sorted_indices]
    
    # Compute DCG
    dcg = 0.0
    for i in range(min(k, len(y_true_sorted))):
        if y_true_sorted[i] == 1:
            dcg += 1.0 / np.log2(i + 2)
    
    # Compute ideal DCG
    ideal_dcg = 0.0
    num_relevant = min(int(np.sum(y_true)), k)
    for i in range(num_relevant):
        ideal_dcg += 1.0 / np.log2(i + 2)
    
    if ideal_dcg == 0:
        return 0.0
    
    return dcg / ideal_dcg


def top_k_precision(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    k: int = 10,
) -> float:
    """Compute precision at k for ranking evaluation.
    
    Args:
        y_true: Ground truth labels (0 or 1).
        y_scores: Predicted scores (higher = more relevant).
        k: Number of top results to consider.
        
    Returns:
        Precision@k score.
    """
    # Sort by scores in descending order
    sorted_indices = np.argsort(-y_scores)
    y_true_sorted = y_true[sorted_indices]
    
    # Compute precision at k
    num_relevant_at_k = np.sum(y_true_sorted[:k])
    return float(num_relevant_at_k / k)
