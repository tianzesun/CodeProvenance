"""Threshold Optimization - single authority for threshold selection."""
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass 
class ThresholdOptimum:
    threshold: float
    method: str
    precision: float
    recall: float
    f1: float

def select_optimal(predictions: List[Dict], truth: List[Dict], method: str = "f2") -> ThresholdOptimum:
    """Select optimal threshold from predictions."""
    from src.evaluation.pr_curve import compute_pr_curve, optimal_threshold
    curve = compute_pr_curve(predictions, truth)
    best = optimal_threshold(curve, method)
    return ThresholdOptimum(
        threshold=best.threshold,
        method=method,
        precision=best.precision,
        recall=best.recall,
        f1=best.f1,
    )
