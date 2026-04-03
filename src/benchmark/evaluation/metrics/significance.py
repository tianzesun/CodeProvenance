"""Statistical significance testing for benchmark evaluation.

Provides bootstrap confidence intervals and McNemar's test for comparing
classifier performance. This module wraps the bootstrap.py functionality
with additional convenience functions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Callable
import numpy as np

from benchmark.evaluation.statistics.bootstrap import (
    bootstrap_confidence_interval,
    bootstrap_metric,
    paired_bootstrap_test,
    BootstrapResult,
)


def mcnemar_test(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
) -> Dict[str, Any]:
    """McNemar's test for comparing two classifiers.
    
    Tests whether classifier A is significantly different from classifier B.
    
    Args:
        y_true: Ground truth labels.
        y_pred_a: Predictions from classifier A.
        y_pred_b: Predictions from classifier B.
        
    Returns:
        Dictionary with test results:
        - statistic: McNemar's test statistic.
        - p_value: Two-tailed p-value.
        - significant: Whether the difference is significant at alpha=0.05.
    """
    # Convert predictions to binary (0/1)
    pred_a = (y_pred_a >= 0.5).astype(int)
    pred_b = (y_pred_b >= 0.5).astype(int)
    
    # Build contingency table
    # b = A correct, B wrong
    # c = A wrong, B correct
    b = np.sum((pred_a == y_true) & (pred_b != y_true))
    c = np.sum((pred_a != y_true) & (pred_b == y_true))
    
    # McNemar's test statistic
    if (b + c) > 0:
        statistic = ((abs(b - c) - 1) ** 2) / (b + c)
    else:
        statistic = 0.0
    
    # Chi-squared distribution with 1 degree of freedom
    # For large samples, use normal approximation
    if (b + c) > 25:
        # Use chi-squared approximation
        from scipy import stats
        p_value = 1 - stats.chi2.cdf(statistic, df=1)
    else:
        # Use exact binomial test for small samples
        from scipy import stats
        p_value = 2 * min(
            stats.binom.cdf(min(b, c), b + c, 0.5),
            1 - stats.binom.cdf(min(b, c) - 1, b + c, 0.5)
        )
    
    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "significant": p_value < 0.05,
        "b": int(b),  # A correct, B wrong
        "c": int(c),  # A wrong, B correct
    }


def add_significance_to_results(
    scores: np.ndarray,
    labels: np.ndarray,
    threshold: float = 0.5,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> Dict[str, Any]:
    """Add significance analysis to benchmark results.
    
    Computes bootstrap confidence intervals for precision, recall, and F1.
    
    Args:
        scores: Similarity scores from the engine.
        labels: Ground truth labels (0 or 1).
        threshold: Decision threshold for classification.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level for intervals.
        seed: Random seed.
        
    Returns:
        Dictionary with significance analysis results.
    """
    # Convert scores to predictions
    predictions = (scores >= threshold).astype(int)
    
    # Define metric functions
    def precision_fn(y_true, y_pred):
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fp = np.sum((y_pred == 1) & (y_true == 0))
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    def recall_fn(y_true, y_pred):
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fn = np.sum((y_pred == 0) & (y_true == 1))
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    def f1_fn(y_true, y_pred):
        prec = precision_fn(y_true, y_pred)
        rec = recall_fn(y_true, y_pred)
        return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    
    def accuracy_fn(y_true, y_pred):
        return np.mean(y_true == y_pred)
    
    # Compute bootstrap confidence intervals
    precision_ci = bootstrap_confidence_interval(
        labels, predictions, precision_fn,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )
    
    recall_ci = bootstrap_confidence_interval(
        labels, predictions, recall_fn,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )
    
    f1_ci = bootstrap_confidence_interval(
        labels, predictions, f1_fn,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )
    
    accuracy_ci = bootstrap_confidence_interval(
        labels, predictions, accuracy_fn,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )
    
    # Compute confusion matrix
    tp = int(np.sum((predictions == 1) & (labels == 1)))
    fp = int(np.sum((predictions == 1) & (labels == 0)))
    tn = int(np.sum((predictions == 0) & (labels == 0)))
    fn = int(np.sum((predictions == 0) & (labels == 1)))
    
    # Compute point estimates
    precision_val = precision_fn(labels, predictions)
    recall_val = recall_fn(labels, predictions)
    f1_val = f1_fn(labels, predictions)
    accuracy_val = accuracy_fn(labels, predictions)
    
    return {
        "precision": {
            "value": float(precision_val),
            "ci_lower": float(precision_ci.ci_lower),
            "ci_upper": float(precision_ci.ci_upper),
            "std": float(precision_ci.std),
        },
        "recall": {
            "value": float(recall_val),
            "ci_lower": float(recall_ci.ci_lower),
            "ci_upper": float(recall_ci.ci_upper),
            "std": float(recall_ci.std),
        },
        "f1": {
            "value": float(f1_val),
            "ci_lower": float(f1_ci.ci_lower),
            "ci_upper": float(f1_ci.ci_upper),
            "std": float(f1_ci.std),
        },
        "accuracy": {
            "value": float(accuracy_val),
            "ci_lower": float(accuracy_ci.ci_lower),
            "ci_upper": float(accuracy_ci.ci_upper),
            "std": float(accuracy_ci.std),
        },
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        },
        "bootstrap_config": {
            "n_bootstrap": n_bootstrap,
            "confidence_level": confidence_level,
            "seed": seed,
        },
    }


def compare_engines_significance(
    y_true: np.ndarray,
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    threshold: float = 0.5,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare two engines with statistical significance testing.
    
    Args:
        y_true: Ground truth labels.
        scores_a: Similarity scores from engine A.
        scores_b: Similarity scores from engine B.
        threshold: Decision threshold for classification.
        n_bootstrap: Number of bootstrap samples.
        seed: Random seed.
        
    Returns:
        Dictionary with comparison results including significance.
    """
    pred_a = (scores_a >= threshold).astype(int)
    pred_b = (scores_b >= threshold).astype(int)
    
    def f1_fn(y_true, y_pred):
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fp = np.sum((y_pred == 1) & (y_true == 0))
        fn = np.sum((y_pred == 0) & (y_true == 1))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    
    # Paired bootstrap test
    bootstrap_result = paired_bootstrap_test(
        y_true, pred_a, pred_b, f1_fn,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    
    # McNemar's test
    mcnemar_result = mcnemar_test(y_true, scores_a, scores_b)
    
    # Point estimates
    f1_a = f1_fn(y_true, pred_a)
    f1_b = f1_fn(y_true, pred_b)
    
    return {
        "engine_a": {
            "f1": float(f1_a),
            "predictions": pred_a.tolist(),
        },
        "engine_b": {
            "f1": float(f1_b),
            "predictions": pred_b.tolist(),
        },
        "difference": {
            "f1_diff": float(f1_a - f1_b),
            "significant": bootstrap_result["significant"],
            "p_value": bootstrap_result["p_value"],
            "ci_lower": bootstrap_result["ci_lower"],
            "ci_upper": bootstrap_result["ci_upper"],
        },
        "mcnemar": mcnemar_result,
        "bootstrap": bootstrap_result,
    }