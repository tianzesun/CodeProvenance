"""Threshold Optimization - single authority for threshold selection."""

from dataclasses import dataclass


@dataclass
class ThresholdOptimum:
    threshold: float
    method: str
    precision: float
    recall: float
    f1: float


def select_optimal(
    predictions: list[dict], truth: list[dict], method: str = "f2"
) -> ThresholdOptimum:
    """Select optimal threshold from predictions."""
    from src.backend.evaluation.pr_curve import compute_pr_curve, optimal_threshold

    curve = compute_pr_curve(predictions, truth)
    best = optimal_threshold(curve, method)
    return ThresholdOptimum(
        threshold=best.threshold,
        method=method,
        precision=best.precision,
        recall=best.recall,
        f1=best.f1,
    )
