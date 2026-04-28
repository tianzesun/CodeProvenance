"""Regression tests for benchmark metric integrity reporting."""

import asyncio
import json

from src.backend.api import server


def test_compute_evaluation_metrics_reports_exact_confusion_matrix() -> None:
    """PAN scorecard metrics should match the labeled score arrays exactly."""
    metrics = server._compute_evaluation_metrics(
        scores=[0.95, 0.82, 0.21, 0.05],
        labels=[3, 2, 0, 0],
        tool_name="integritydesk",
        dataset_name="unit",
    )

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["confusion_matrix"] == {"tp": 1, "fp": 0, "tn": 1, "fn": 0}
    assert metrics["split_protocol"]["protocol"] == (
        "deterministic_stratified_calibration_holdout"
    )
    assert metrics["split_protocol"]["holdout_positive_pairs"] == 1
    assert metrics["split_protocol"]["holdout_negative_pairs"] == 1
    assert metrics["metric_integrity"]["label_count_matches_score_count"] is True
    assert metrics["metric_integrity"]["positive_pairs"] == 2
    assert metrics["metric_integrity"]["negative_pairs"] == 2


def test_compute_evaluation_metrics_exposes_fixed_threshold_baseline() -> None:
    """Calibration output should show when optimized F1 beats fixed-threshold F1."""
    metrics = server._compute_evaluation_metrics(
        scores=[0.90, 0.40, 0.30, 0.20],
        labels=[3, 2, 0, 0],
        tool_name="integritydesk",
        dataset_name="unit",
    )

    assert metrics["best_threshold_exact"] == 0.300001
    assert metrics["confusion_matrix"] == {"tp": 1, "fp": 0, "tn": 1, "fn": 0}
    assert metrics["fixed_threshold_metrics"]["confusion_matrix"] == {
        "tp": 0,
        "fp": 0,
        "tn": 1,
        "fn": 1,
    }
    assert metrics["metric_integrity"]["calibration_bias_warning"] is True
    assert metrics["metric_integrity"]["fixed_threshold_f1"] < metrics["f1_score"]
    assert metrics["metric_integrity"]["heldout_f1"] == metrics["f1_score"]


def test_binary_metrics_at_threshold_uses_inclusive_boundary() -> None:
    """Scores equal to the threshold should count as positive predictions."""
    metrics = server._binary_metrics_at_threshold(
        scores_arr=server.np.array([0.5, 0.49]),
        labels_arr=server.np.array([1, 0]),
        threshold=0.5,
    )

    assert metrics["confusion_matrix"] == {"tp": 1, "fp": 0, "tn": 1, "fn": 0}
    assert metrics["f1_score"] == 1.0


def test_fixed_threshold_strategy_does_not_optimize_regression_threshold() -> None:
    """Regression tests should use the fixed production threshold."""
    metrics = server._compute_evaluation_metrics(
        scores=[0.90, 0.40, 0.30, 0.20],
        labels=[3, 2, 0, 0],
        tool_name="integritydesk",
        dataset_name="unit",
        threshold_strategy="fixed_threshold",
    )

    assert metrics["threshold_strategy"] == "fixed_threshold"
    assert metrics["best_threshold_exact"] == 0.5
    assert metrics["confusion_matrix"] == {"tp": 0, "fp": 0, "tn": 1, "fn": 1}
    assert metrics["metric_integrity"]["calibration_bias_warning"] is False


def test_regression_quality_gates_fail_on_low_precision() -> None:
    """Regression quality gates should fail metrics below configured thresholds."""
    gates = server._build_regression_quality_gates(
        {
            "precision": 0.5,
            "recall": 1.0,
            "f1_score": 0.66,
            "false_positive_rate": 0.5,
        }
    )

    assert gates["passed"] is False
    assert gates["passed_count"] == 1
    failed = {gate["metric"] for gate in gates["gates"] if not gate["passed"]}
    assert failed == {"precision", "f1_score", "false_positive_rate"}


def test_benchmark_dataset_listing_hides_unrunnable_datasets() -> None:
    """Dataset cards should only expose benchmark-runnable labeled pair datasets."""

    async def load_dataset_ids() -> set[str]:
        response = await server.get_benchmark_datasets()
        payload = json.loads(response.body)
        return {dataset["id"] for dataset in payload["datasets"]}

    dataset_ids = asyncio.run(load_dataset_ids())

    assert "kaggle_student_code" in dataset_ids
    assert "synthetic" in dataset_ids
    assert "xiangtan" in dataset_ids
    assert "poj104" in dataset_ids
    assert "poolc_600k_python" in dataset_ids
    assert "codexglue_clone" not in dataset_ids
    assert "google_codejam" not in dataset_ids
    assert "codesearchnet" not in dataset_ids


def test_xiangtan_loader_produces_positive_and_negative_pairs(tmp_path) -> None:
    """Xiangtan should be usable as a labeled Java benchmark dataset."""
    submissions, pairs = server._load_xiangtan_pair_dataset(
        server.BENCHMARK_DATA_DIR / "xiangtan", tmp_path
    )

    labels = [pair["label"] for pair in pairs]

    assert submissions
    assert any(label >= 2 for label in labels)
    assert any(label == 0 for label in labels)
    assert len(labels) > 75
