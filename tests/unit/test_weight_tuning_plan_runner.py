"""Tests for the plan-aligned weight tuning runner."""

import json

from src.backend.benchmark.runners.weight_tuning_plan_runner import (
    DEFAULT_WEIGHTS,
    ENGINE_NAMES,
    ScoredPair,
    generate_grid_weights,
    metrics_at_threshold,
    normalize_weights,
    penalized_objective,
    run_weight_tuning_plan,
    stratified_split,
    weighted_score,
)


def test_normalize_weights_returns_simplex():
    """Weights are non-negative and sum to one."""
    normalized = normalize_weights({"ast": 2.0, "fingerprint": 1.0, "embedding": -3.0})

    assert set(normalized) == set(ENGINE_NAMES)
    assert round(sum(normalized.values()), 6) == 1.0
    assert normalized["ast"] == 2.0 / 3.0
    assert normalized["fingerprint"] == 1.0 / 3.0
    assert normalized["embedding"] == 0.0


def test_weighted_score_uses_engine_scores():
    """Weighted score combines canonical engine values."""
    pair = ScoredPair(
        pair_id="p1",
        file_a="a.py",
        file_b="b.py",
        label=1,
        scores={
            "ast": 1.0,
            "fingerprint": 0.5,
            "embedding": 0.0,
            "execution": 0.0,
            "ngram": 0.0,
        },
    )

    assert weighted_score(pair, {"ast": 0.5, "fingerprint": 0.5}) == 0.75


def test_metrics_at_threshold_counts_confusion_matrix():
    """Binary metrics include the false-positive rate used by the objective."""
    metrics = metrics_at_threshold(
        scores=[0.9, 0.8, 0.7, 0.2],
        labels=[1, 0, 1, 0],
        threshold=0.75,
    )

    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1
    assert metrics.true_negatives == 1
    assert metrics.false_positive_rate == 0.5


def test_penalized_objective_penalizes_high_fpr():
    """The plan objective subtracts sharply when FPR exceeds the limit."""
    assert penalized_objective(0.9, 0.02, fpr_limit=0.03, fpr_penalty=10.0) == 0.9
    assert penalized_objective(0.9, 0.08, fpr_limit=0.03, fpr_penalty=10.0) == 0.4


def test_stratified_split_preserves_both_classes():
    """Train and test splits keep positives and negatives represented."""
    pairs = [
        ScoredPair(f"pos_{index}", "a.py", "b.py", 1, dict(DEFAULT_WEIGHTS))
        for index in range(10)
    ] + [
        ScoredPair(f"neg_{index}", "a.py", "c.py", 0, dict(DEFAULT_WEIGHTS))
        for index in range(10)
    ]

    train, test = stratified_split(pairs, train_ratio=0.7, seed=7)

    assert len(train) == 14
    assert len(test) == 6
    assert {pair.label for pair in train} == {0, 1}
    assert {pair.label for pair in test} == {0, 1}


def test_generate_grid_weights_obeys_bounds():
    """Grid search emits only normalized combinations inside engine bounds."""
    bounds = {engine: (0.0, 1.0) for engine in ENGINE_NAMES}
    combinations = list(generate_grid_weights(grid_step=0.5, bounds=bounds))

    assert combinations
    assert all(round(sum(weights.values()), 6) == 1.0 for weights in combinations)


def test_run_weight_tuning_plan_writes_expected_artifacts(tmp_path):
    """End-to-end runner creates the key plan deliverables."""
    rows = []
    for index in range(8):
        rows.append(
            {
                "pair_id": f"pos_{index}",
                "file_a": "a.py",
                "file_b": "b.py",
                "label": 1,
                "ast": 0.90,
                "fingerprint": 0.85,
                "embedding": 0.80,
                "execution": 0.75,
                "ngram": 0.70,
            }
        )
        rows.append(
            {
                "pair_id": f"neg_{index}",
                "file_a": "a.py",
                "file_b": "c.py",
                "label": 0,
                "ast": 0.10,
                "fingerprint": 0.15,
                "embedding": 0.20,
                "execution": 0.05,
                "ngram": 0.15,
            }
        )
    input_path = tmp_path / "pairs.json"
    input_path.write_text(json.dumps(rows), encoding="utf-8")
    output_dir = tmp_path / "results"

    summary = run_weight_tuning_plan(
        scored_pairs_path=input_path,
        output_dir=output_dir,
        grid_step=0.5,
        max_grid_runs=12,
    )

    assert summary["pair_count"] == 16
    assert (output_dir / "train_pairs.json").exists()
    assert (output_dir / "test_pairs.json").exists()
    assert (output_dir / "baseline.json").exists()
    assert (output_dir / "solo_summary.csv").exists()
    assert (output_dir / "search_log.csv").exists()
    assert (output_dir / "best_weights_search.json").exists()
    assert (output_dir / "threshold_sweep.csv").exists()
    assert (output_dir / "best_threshold.json").exists()
    assert (output_dir / "final_evaluation.json").exists()
