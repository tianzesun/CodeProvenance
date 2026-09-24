"""Unit tests for basic benchmark classification metrics.

Covers the FPR/TPR fields the benchmark taxonomy reports for §1 detection
performance and §2 false-positive validation.
"""

from __future__ import annotations

import pytest

from src.backend.benchmark.evaluation.metrics import (
    compute_metrics_from_confusion,
    false_positive_rate,
    recall,
    true_positive_rate,
)


class TestFalsePositiveRate:
    """FPR = FP / (FP + TN) over the human-only denominator."""

    def test_share_of_human_samples_flagged(self) -> None:
        assert false_positive_rate(3, 7) == pytest.approx(0.3)

    def test_no_human_samples_is_zero(self) -> None:
        assert false_positive_rate(0, 0) == 0.0

    def test_all_human_samples_flagged_is_one(self) -> None:
        assert false_positive_rate(5, 0) == 1.0

    def test_no_false_positives_is_zero(self) -> None:
        assert false_positive_rate(0, 12) == 0.0


class TestTruePositiveRate:
    """TPR is the ROC-convention name for recall."""

    def test_matches_recall(self) -> None:
        assert true_positive_rate(3, 1) == pytest.approx(recall(3, 1))

    def test_no_ai_samples_is_zero(self) -> None:
        assert true_positive_rate(0, 0) == 0.0


class TestComputeMetricsFromConfusion:
    """The aggregate metric payload must expose TPR/FPR and raw counts."""

    def test_exposes_tpr_fpr_and_counts(self) -> None:
        metrics = compute_metrics_from_confusion({"tp": 5, "fp": 2, "tn": 8, "fn": 3})
        assert metrics["tpr"] == pytest.approx(0.625)
        assert metrics["fpr"] == pytest.approx(0.2)
        assert metrics["recall"] == metrics["tpr"]
        assert metrics["precision"] == pytest.approx(5 / 7)
        assert metrics["accuracy"] == pytest.approx(13 / 18)
        assert metrics["tp"] == 5
        assert metrics["fp"] == 2
        assert metrics["tn"] == 8
        assert metrics["fn"] == 3

    def test_perfect_classifier(self) -> None:
        metrics = compute_metrics_from_confusion({"tp": 4, "fp": 0, "tn": 6, "fn": 0})
        assert metrics["fpr"] == 0.0
        assert metrics["tpr"] == 1.0
        assert metrics["f1"] == 1.0

    def test_degenerate_empty_confusion(self) -> None:
        metrics = compute_metrics_from_confusion({"tp": 0, "fp": 0, "tn": 0, "fn": 0})
        assert metrics["fpr"] == 0.0
        assert metrics["tpr"] == 0.0
        assert metrics["accuracy"] == 0.0
