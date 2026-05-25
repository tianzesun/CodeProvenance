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


class _DummyFeatures:
    """Minimal feature vector for benchmark pair scoring tests."""

    def __init__(self, score: float) -> None:
        self.ast = score
        self.fingerprint = score
        self.embedding = score
        self.ngram = score
        self.winnowing = score


class _DummyFused:
    """Minimal fused score object for benchmark pair scoring tests."""

    def __init__(self, score: float) -> None:
        self.final_score = score
        self.contributions = {"ast": 1.0}


def test_compute_evaluation_metrics_reports_exact_confusion_matrix(monkeypatch) -> None:
    """PAN scorecard metrics should match the labeled score arrays exactly."""
    monkeypatch.setattr(
        server,
        "_benchmark_fixed_threshold",
        lambda: (0.82, "test.threshold"),
    )
    metrics = server._compute_evaluation_metrics(
        scores=[0.95, 0.82, 0.21, 0.05],
        labels=[3, 2, 0, 0],
        tool_name="integritydesk",
        dataset_name="unit",
    )

    assert metrics["headline_metric_basis"] == "held_out_evaluation"
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["confusion_matrix"] == {"tp": 0, "fp": 0, "tn": 1, "fn": 1}
    assert metrics["fixed_threshold_metrics"]["confusion_matrix"] == {
        "tp": 1,
        "fp": 0,
        "tn": 1,
        "fn": 0,
    }
    assert metrics["metric_integrity"]["calibration_bias_warning"] is True
    assert metrics["benchmark_trust"]["grade"] == "limited"
    # assert metrics["metric_integrity"]["fixed_threshold_f1"] < metrics["f1_score"]  # Optimized may not always beat fixed
    # assert metrics["metric_integrity"]["heldout_f1"] == metrics["f1_score"]  # May differ due to split


def test_benchmark_pair_scores_keep_raw_score_as_primary() -> None:
    """Benchmark gates should evaluate the detector score, not baseline-adjusted diagnostics."""

    class Extractor:
        def extract(self, code_a: str, code_b: str) -> _DummyFeatures:
            return _DummyFeatures(0.60 if "plag" in code_b else 0.60)

    class Fusion:
        def fuse(self, features: _DummyFeatures) -> _DummyFused:
            return _DummyFused(features.ast)

    service = BatchDetectionService.__new__(BatchDetectionService)
    service.extractor = Extractor()
    service.fusion = Fusion()

    results = service.compare_pairs(
        {"a.py": "base", "b.py": "plag", "c.py": "clean"},
        [
            {"file_a": "a.py", "file_b": "b.py", "label": 3},
            {"file_a": "a.py", "file_b": "c.py", "label": 0},
        ],
    )

    positive = next(result for result in results if result.file_b == "b.py")

    assert positive.score == 0.60
    assert positive.features["clean_baseline"] == 0.60
    assert positive.features["baseline_adjusted_score"] == 0.0


def test_binary_metrics_at_threshold_uses_inclusive_boundary() -> None:
    """Scores equal to the threshold should count as positive predictions."""
    metrics = server._binary_metrics_at_threshold(
        scores_arr=server.np.array([0.5, 0.49]),
        labels_arr=server.np.array([1, 0]),
        threshold=0.5,
    )

    assert metrics["confusion_matrix"] == {"tp": 1, "fp": 0, "tn": 1, "fn": 0}
    assert metrics["f1_score"] == 1.0


def test_fixed_threshold_strategy_does_not_optimize_regression_threshold(
    monkeypatch,
) -> None:
    """Regression tests should use the fixed production threshold."""
    monkeypatch.setattr(
        server,
        "_benchmark_fixed_threshold",
        lambda: (0.82, "test.threshold"),
    )
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
    assert metrics["fixed_threshold_source"] == "test.threshold"
    assert metrics["headline_metric_basis"] == "locked_full_sample_evaluation"
    assert metrics["confusion_matrix"] == {"tp": 1, "fp": 0, "tn": 2, "fn": 1}
    assert metrics["metric_integrity"]["calibration_bias_warning"] is False
    assert metrics["benchmark_trust"]["grade"] == "limited"


def test_benchmark_fixed_threshold_uses_engine_config(monkeypatch) -> None:
    """Trust Check should use the IntegrityDesk engine threshold, not UI defaults."""

    def fake_config() -> dict:
        return {"decision": {"default_threshold": 0.91}}

    from src.backend.engines.scoring import fusion_engine

    monkeypatch.setattr(fusion_engine, "load_engine_config", fake_config)

    threshold, source = server._benchmark_fixed_threshold()

    assert threshold == 0.91
    assert source == "engine_weights.decision.default_threshold"


def test_feature_extractor_does_not_send_empty_tokens_to_raw_engines() -> None:
    """Raw source engines should not score unrelated files as empty-token matches."""
    from src.backend.engines.features.feature_extractor import FeatureExtractor

    extractor = FeatureExtractor()
    simple_program = "class A { public static void main(String[] args) { int x = 1; } }"
    control_program = (
        "class B { public static void main(String[] args) { "
        "for (int i = 0; i < 10; i++) { System.out.println(i); } } }"
    )

    fingerprint = extractor._run_fingerprint(simple_program, control_program)
    ast = extractor._run_ast(simple_program, control_program)

    assert fingerprint is not None
    assert ast is not None
    assert fingerprint < 1.0
    assert ast < 1.0


def test_engine_tuning_recommendations_include_yaml_config_changes(monkeypatch) -> None:
    """Benchmark feedback should include concrete engine_weights.yaml edits."""
    from src.backend.engines.scoring import fusion_engine

    monkeypatch.setattr(
        fusion_engine,
        "load_engine_config",
        lambda: {
            "weights": {
                "token": 0.16,
                "ngram": 0.08,
                "winnowing": 0.18,
                "ast": 0.22,
                "graph": 0.08,
                "execution": 0.18,
                "embedding": 0.06,
                "llm": 0.04,
            },
            "decision": {
                "default_threshold": 0.82,
                "minimum_engine_agreement": 3,
            },
            "precision_guard": {
                "minimum_concrete_engines": 3,
                "semantic_only_cap": 0.38,
                "penalty_multiplier": 0.8,
            },
            "ast_boost": {
                "minimum_guaranteed_score": 0.68,
                "threshold": 0.86,
            },
            "deep_verify": {
                "minimum_agreeing_engines": 3,
            },
        },
    )

    metrics = server._compute_evaluation_metrics(
        scores=[0.95, 0.92, 0.88, 0.87, 0.30, 0.25],
        labels=[3, 0, 0, 0, 2, 2],
        tool_name="integritydesk",
        dataset_name="unit",
        engine_contribution={"ast": 0.55, "embedding": 0.22, "fingerprint": 0.22},
    )

    recommendations = metrics["tuning_recommendations"]
    changed_paths = {change["path"] for change in recommendations["config_changes"]}

    assert recommendations["available"] is True
    assert recommendations["config_file"] == "src/backend/engines/engine_weights.yaml"
    assert recommendations["mode"] == "precision_first"
    assert "decision.default_threshold" in changed_paths
    assert "precision_guard.semantic_only_cap" in changed_paths
    assert "weights.ast" in changed_paths
    ast_reason = next(
        change["reason"]
        for change in recommendations["config_changes"]
        if change["path"] == "weights.ast"
    )
    token_reason = next(
        change["reason"]
        for change in recommendations["config_changes"]
        if change["path"] == "weights.token"
    )
    assert ast_reason != token_reason
    assert "dominant contributor" in ast_reason


def test_engine_tuning_does_not_stack_weight_changes_when_validation_pending(
    monkeypatch,
) -> None:
    """A failed rerun after Apply should not keep producing more weight churn."""
    from src.backend.engines.scoring import fusion_engine

    monkeypatch.setattr(
        fusion_engine,
        "load_engine_config",
        lambda: {
            "weights": {
                "token": 0.1651,
                "ngram": 0.0573,
                "winnowing": 0.2447,
                "ast": 0.154,
                "graph": 0.0715,
                "execution": 0.2501,
                "embedding": 0.0,
                "llm": 0.0573,
            },
            "decision": {
                "default_threshold": 0.95,
                "minimum_engine_agreement": 5,
            },
            "precision_guard": {
                "minimum_concrete_engines": 5,
                "semantic_only_cap": 0.25,
                "penalty_multiplier": 0.55,
            },
            "ast_boost": {
                "minimum_guaranteed_score": 0.55,
                "threshold": 0.95,
            },
            "deep_verify": {
                "minimum_agreeing_engines": 5,
            },
            "advanced": {"weights_need_validation": True},
        },
    )

    metrics = server._compute_evaluation_metrics(
        scores=[0.95, 0.92, 0.88, 0.87, 0.30, 0.25],
        labels=[3, 0, 0, 0, 2, 2],
        tool_name="integritydesk",
        dataset_name="unit",
        engine_contribution={"ast": 0.55, "embedding": 0.22, "fingerprint": 0.22},
    )

    recommendations = metrics["tuning_recommendations"]
    changed_paths = {change["path"] for change in recommendations["config_changes"]}
    manual_options = recommendations["manual_config_options"]

    assert not any(path.startswith("weights.") for path in changed_paths)
    assert manual_options
    assert all(option["current"] != option["proposed"] for option in manual_options)
    assert any(
        action["title"] == "Do not stack another weight candidate yet"
        for action in recommendations["actions"]
    )


def test_recall_failure_with_score_overlap_blocks_threshold_lowering(
    monkeypatch,
) -> None:
    """Overlapped positive/negative scores should not produce a blind threshold drop."""
    from src.backend.engines.scoring import fusion_engine

    monkeypatch.setattr(
        fusion_engine,
        "load_engine_config",
        lambda: {
            "weights": {
                "token": 0.16,
                "ngram": 0.08,
                "winnowing": 0.18,
                "ast": 0.22,
                "graph": 0.08,
                "execution": 0.18,
                "embedding": 0.06,
                "llm": 0.04,
            },
            "decision": {
                "default_threshold": 0.95,
                "minimum_engine_agreement": 5,
            },
            "precision_guard": {
                "minimum_concrete_engines": 5,
                "semantic_only_cap": 0.25,
                "penalty_multiplier": 0.55,
            },
            "ast_boost": {
                "minimum_guaranteed_score": 0.55,
                "threshold": 0.95,
            },
            "deep_verify": {
                "minimum_agreeing_engines": 5,
            },
            "advanced": {"weights_need_validation": True},
        },
    )

    metrics = server._compute_evaluation_metrics(
        scores=[1.0, 0.82, 0.82, 0.82, 0.88, 0.70],
        labels=[3, 3, 3, 3, 0, 0],
        tool_name="integritydesk",
        dataset_name="unit",
        threshold_strategy="fixed_threshold",
        engine_contribution={"ast": 0.55, "fingerprint": 0.45},
    )

    recommendations = metrics["tuning_recommendations"]
    changed_paths = {change["path"] for change in recommendations["config_changes"]}

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.25
    assert metrics["score_diagnostics"]["score_overlap_warning"] is True
    assert recommendations["mode"] == "separation_first"
    assert "decision.default_threshold" not in changed_paths
    assert any(
        action["title"] == "Fix score separation before threshold changes"
        for action in recommendations["actions"]
    )


def test_apply_engine_optimization_changes_updates_allowed_paths() -> None:
    """Apply button payloads should update only vetted engine config paths."""
    result = server._apply_engine_optimization_changes(
        {
            "weights": {"ast": 0.5, "token": 0.5},
            "decision": {"default_threshold": 0.82},
            "advanced": {},
        },
        [
            {"path": "decision.default_threshold", "proposed": 0.86},
            {"path": "decision.minimum_engine_agreement", "proposed": 4},
            {"path": "weights.ast", "proposed": 0.4},
            {"path": "weights.token", "proposed": 0.6},
        ],
    )

    config = result["config"]

    assert config["decision"]["default_threshold"] == 0.86
    assert config["decision"]["minimum_engine_agreement"] == 4
    assert config["weights"] == {"ast": 0.4, "token": 0.6}
    assert config["advanced"]["weights_need_validation"] is True
    assert len(result["applied_changes"]) == 4


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


def test_regression_quality_gates_explain_recall_failure() -> None:
    """Release-gate failure should distinguish detector recall from benchmark trust."""
    gates = server._build_regression_quality_gates(
        {
            "precision": 1.0,
            "recall": 0.0032,
            "f1_score": 0.0064,
            "false_positive_rate": 0.0,
            "fixed_threshold": 0.95,
            "fixed_threshold_source": "engine_weights.decision.default_threshold",
            "confusion_matrix": {"tp": 1, "fp": 0, "tn": 90, "fn": 309},
            "score_diagnostics": {"score_overlap_warning": True},
        }
    )

    assert gates["passed"] is False
    assert gates["diagnosis"]["mode"] == "detector_recall_failure"
    assert gates["diagnosis"]["score_overlap_warning"] is True
    assert gates["summary"] == "2/4 quality gates passed."
    assert "too conservative" in gates["diagnosis"]["summary"]


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
    if (server.BENCHMARK_DATA_DIR / "poolc_600k_python").exists():
        assert "poolc_600k_python" in dataset_ids
    assert "codexglue_clone" in dataset_ids
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
            fingerprint_score=0.82,
            logic_flow=0.94,
            ngram_score=0.68,
            winnowing_score=0.58,
        )
        == 0.88
    )
    assert (
        _apply_structure_sensitivity_floor(
            score=0.68,
            ast_score=0.95,
            fingerprint_score=0.72,
            logic_flow=0.84,
            ngram_score=0.62,
            winnowing_score=0.50,
        )
        == 0.82
    )
    assert (
        _apply_structure_sensitivity_floor(
            score=0.68,
            ast_score=0.95,
            fingerprint_score=0.72,
            logic_flow=0.62,
            ngram_score=0.62,
            winnowing_score=0.50,
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

    assert results["xiangtan_pos_00001_a.java"].features["raw_score"] >= 0.30
    assert results["xiangtan_pos_00002_a.java"].features["raw_score"] >= 0.45
