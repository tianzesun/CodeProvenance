"""Regression tests for benchmark metric integrity reporting."""

import asyncio
import json

from src.backend.application.services.batch_detection_service import (
    BatchDetectionService,
    DECISION_BLOCK_TOKEN,
    ITERATIVE_BLOCK_TOKEN,
    _apply_structure_sensitivity_floor,
    _clean_similarity_baseline,
    _logic_flow_tokens,
    _logic_flow_similarity,
    _subtract_clean_baseline,
)
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
    assert metrics["best_threshold_exact"] == 0.82
    assert metrics["fixed_threshold"] == 0.82
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


def test_normalize_benchmark_protocol_supports_new_product_names() -> None:
    """Protocol normalization should accept the new product-facing mode names."""
    development = server._normalize_benchmark_protocol("development")
    release = server._normalize_benchmark_protocol("release_check")
    comparison = server._normalize_benchmark_protocol("comparison")

    assert development == {
        "benchmark_type": "pan_optimization",
        "protocol": "development_evaluation",
        "threshold_policy": "optimize_on_calibration",
        "optimization_objective": "f1",
        "report_type": "development_evaluation_report",
    }
    assert release == {
        "benchmark_type": "regression_test",
        "protocol": "release_check",
        "threshold_policy": "locked_threshold",
        "optimization_objective": "fixed_threshold_guard",
        "report_type": "release_check_report",
    }
    assert comparison == {
        "benchmark_type": "tool_comparison",
        "protocol": "tool_comparison",
        "threshold_policy": "per_tool_scores",
        "optimization_objective": "comparative_analysis",
        "report_type": "tool_comparison_report",
    }


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


def test_xiangtan_negative_pairs_use_different_behavior_signatures(tmp_path) -> None:
    """Xiangtan negatives must not pair same-solution aliases as false negatives."""
    submissions, pairs = server._load_xiangtan_pair_dataset(
        server.BENCHMARK_DATA_DIR / "xiangtan", tmp_path
    )

    negative_pairs = [pair for pair in pairs if pair["label"] == 0]

    assert negative_pairs
    for pair in negative_pairs:
        signature_a = server._java_behavior_signature(submissions[pair["file_a"]])
        signature_b = server._java_behavior_signature(submissions[pair["file_b"]])
        assert signature_a != signature_b


def test_clean_baseline_subtraction_treats_normal_similarity_as_zero() -> None:
    """Labeled clean-pair similarity should become the benchmark zero point."""
    baseline = _clean_similarity_baseline([0.84, 0.85, 0.86])

    assert baseline == 0.85
    assert _subtract_clean_baseline(0.85, baseline) == 0.0
    assert round(_subtract_clean_baseline(0.925, baseline), 3) == 0.5


def test_logic_flow_signature_distinguishes_common_skeleton_from_logic_match() -> None:
    """Shared Java method skeletons should be explainable as normal similarity."""
    sum_code = """
public class ArraySum {
    public int sumArray(int[] arr) {
        int total = 0;
        for (int i = 0; i < arr.length; i++) {
            total += arr[i];
        }
        return total;
    }
}
"""
    max_code = """
public class MaxFinder {
    public int findMax(int[] arr) {
        int max = arr[0];
        for (int i = 1; i < arr.length; i++) {
            if (arr[i] > max) {
                max = arr[i];
            }
        }
        return max;
    }
}
"""

    logic_flow = _logic_flow_similarity(sum_code, max_code)

    assert logic_flow < 0.72


def test_for_and_while_normalize_to_iterative_block() -> None:
    """For/while rewrites should preserve control-flow similarity."""
    for_loop = """
for (int i = 0; i < items.length; i++) {
    total += items[i];
}
"""
    while_loop = """
int i = 0;
while (i < items.length) {
    total += items[i];
    i++;
}
"""

    assert ITERATIVE_BLOCK_TOKEN in _logic_flow_tokens(for_loop)
    assert ITERATIVE_BLOCK_TOKEN in _logic_flow_tokens(while_loop)
    assert "for" not in _logic_flow_tokens(for_loop)
    assert "while" not in _logic_flow_tokens(while_loop)
    assert _logic_flow_similarity(for_loop, while_loop) >= 0.75


def test_if_and_switch_normalize_to_decision_block() -> None:
    """If/switch rewrites should be treated as decision blocks."""
    if_code = """
if (score > 90) {
    grade = 1;
} else {
    grade = 0;
}
"""
    switch_code = """
switch (bucket) {
    case 9:
        grade = 1;
        break;
    default:
        grade = 0;
}
"""

    assert DECISION_BLOCK_TOKEN in _logic_flow_tokens(if_code)
    assert DECISION_BLOCK_TOKEN in _logic_flow_tokens(switch_code)
    assert "if" not in _logic_flow_tokens(if_code)
    assert "switch" not in _logic_flow_tokens(switch_code)
    assert _logic_flow_similarity(if_code, switch_code) >= 0.35


def test_logic_flow_strips_comments_before_matching() -> None:
    """Comments should not inflate or deflate structural similarity."""
    base_code = """
int total = 0;
for (int i = 0; i < nums.length; i++) {
    total += nums[i];
}
return total;
"""
    commented_code = """
// The following loop walks through the array.
int total = 0;
for (int i = 0; i < nums.length; i++) {
    /* This comment should not become punctuation evidence. */
    total += nums[i];
}
return total; // done
"""

    assert _logic_flow_tokens(base_code) == _logic_flow_tokens(commented_code)
    assert _logic_flow_similarity(base_code, commented_code) == 1.0


def test_structure_sensitivity_floor_keeps_reorder_and_control_flow_matches() -> None:
    """Strong structural evidence should survive stricter precision tuning."""
    assert (
        _apply_structure_sensitivity_floor(
            score=0.68,
            ast_score=0.95,
            fingerprint_score=0.72,
            logic_flow=0.94,
        )
        == 0.88
    )
    assert (
        _apply_structure_sensitivity_floor(
            score=0.68,
            ast_score=0.95,
            fingerprint_score=0.72,
            logic_flow=0.84,
        )
        == 0.82
    )
    assert (
        _apply_structure_sensitivity_floor(
            score=0.68,
            ast_score=0.95,
            fingerprint_score=0.72,
            logic_flow=0.62,
        )
        == 0.68
    )


def test_xiangtan_renamed_and_structured_pairs_remain_detectable(tmp_path) -> None:
    """Type-2 rename gains should not come at the expense of Type-3 structure."""
    submissions, pairs = server._load_xiangtan_pair_dataset(
        server.BENCHMARK_DATA_DIR / "xiangtan", tmp_path
    )
    selected_pairs = [
        pair
        for pair in pairs
        if pair["file_a"] in {"xiangtan_pos_00001_a.java", "xiangtan_pos_00002_a.java"}
    ]

    results = {
        result.file_a: result
        for result in BatchDetectionService(threshold=0.3).compare_pairs(
            submissions, selected_pairs
        )
    }

    assert results["xiangtan_pos_00001_a.java"].features["raw_score"] >= 0.88
    assert results["xiangtan_pos_00002_a.java"].features["raw_score"] >= 0.82
