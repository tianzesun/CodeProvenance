"""Tests for professor-workflow accuracy proof metrics."""

from src.backend.evaluation.proof_system import (
    AccuracyProofSystem,
    ProofCase,
    category_false_positive_rate,
    precision_at_k,
    recall_at_fixed_fpr,
)


def _release_ready_cases():
    positives = [
        ProofCase(f"p{i}", 0.99 - i * 0.01, 1, "direct_copy") for i in range(18)
    ]
    positives += [
        ProofCase("same_bug_1", 0.91, 1, "same_bug"),
        ProofCase("same_bug_2", 0.90, 1, "same_bug"),
        ProofCase("previous_1", 0.89, 1, "previous_semester_reuse"),
        ProofCase("previous_2", 0.88, 1, "previous_semester_reuse"),
    ]
    hard_negatives = [
        ProofCase(f"starter_{i}", 0.30 + i * 0.01, 0, "starter_code_false_positive")
        for i in range(10)
    ]
    hard_negatives += [
        ProofCase(f"common_{i}", 0.25 + i * 0.01, 0, "common_solution_false_positive")
        for i in range(10)
    ]
    easy_negatives = [
        ProofCase(f"n{i}", 0.10 + i * 0.005, 0, "unrelated") for i in range(30)
    ]
    return positives + hard_negatives + easy_negatives


def test_precision_at_k_measures_top_queue_quality() -> None:
    """Precision@k should operate on ranked review cases."""
    cases = [
        ProofCase("a", 0.9, 1, "direct_copy"),
        ProofCase("b", 0.8, 0, "starter_code_false_positive"),
        ProofCase("c", 0.7, 1, "same_bug"),
    ]

    assert precision_at_k(cases, 2) == 0.5


def test_fixed_fpr_recall_uses_thresholds_that_respect_false_positive_budget() -> None:
    """Recall at fixed FPR should not count thresholds with too many false positives."""
    cases = [
        ProofCase("p1", 0.95, 1, "direct_copy"),
        ProofCase("p2", 0.80, 1, "same_bug"),
        ProofCase("n1", 0.70, 0, "unrelated"),
        ProofCase("n2", 0.10, 0, "unrelated"),
    ]

    assert recall_at_fixed_fpr(cases, 0.0) == 1.0


def test_hard_negative_false_positive_rate_is_category_specific() -> None:
    """Hard-negative FPR should ignore ordinary negatives."""
    cases = [
        ProofCase("starter_high", 0.9, 0, "starter_code_false_positive"),
        ProofCase("starter_low", 0.2, 0, "starter_code_false_positive"),
        ProofCase("ordinary_high", 0.9, 0, "unrelated"),
    ]

    assert (
        category_false_positive_rate(cases, {"starter_code_false_positive"}, 0.75)
        == 0.5
    )


def test_accuracy_proof_system_passes_release_gates_for_strong_run() -> None:
    """A strong run with discounted hard negatives should pass launch gates."""
    baseline = [
        ProofCase(f"starter_base_{i}", 0.9, 0, "starter_code_false_positive")
        for i in range(10)
    ]
    report = AccuracyProofSystem().evaluate(
        _release_ready_cases(),
        baseline_cases=baseline,
    )

    assert report.release_ready is True
    assert report.metrics["precision_at_10"] == 1.0
    assert report.metrics["precision_at_20"] == 1.0
    assert report.metrics["starter_code_false_positive_reduction"] == 1.0


def test_accuracy_proof_system_fails_embedding_only_high_risk_gate() -> None:
    """Embedding-only high-risk rows should block production release."""
    cases = _release_ready_cases() + [
        ProofCase(
            "embedding_only",
            0.95,
            0,
            "unrelated",
            metadata={"embedding_only": True},
        )
    ]
    report = AccuracyProofSystem().evaluate(cases)

    assert report.release_ready is False
    assert report.metrics["embedding_only_high_risk_count"] == 1.0
    assert any(
        result.metric == "embedding_only_high_risk_count" and not result.passed
        for result in report.gate_results
    )


def test_ablation_report_compares_layer_variants() -> None:
    """Ablation output should compare layer variants with the same metrics."""
    system = AccuracyProofSystem()
    variants = {
        "layer_a_only": [
            ProofCase("starter_fp", 0.95, 0, "starter_code_false_positive"),
            ProofCase("copy", 0.90, 1, "direct_copy"),
        ],
        "full_system": [
            ProofCase("copy", 0.90, 1, "direct_copy"),
            ProofCase("starter_fp", 0.20, 0, "starter_code_false_positive"),
        ],
    }

    ablations = system.run_ablations(variants)

    assert set(ablations) == {"layer_a_only", "full_system"}
    assert ablations["full_system"]["hard_negative_false_positive_rate"] == 0.0
    assert ablations["layer_a_only"]["hard_negative_false_positive_rate"] == 1.0
