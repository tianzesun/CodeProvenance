"""Tests for the engine-evaluation harness (corpus routing and tool batching)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from src.backend.benchmark.runners.engine_evaluation_runner import (
    EngineEvaluationRunner,
    LabeledPair,
)


def _pair(index: int, label: int, language: str = "java") -> LabeledPair:
    """Build one labeled pair with distinguishable code."""
    return LabeledPair(
        pair_id=f"pair-{index}",
        code_a=f"code a {index}",
        code_b=f"code b {index}",
        label=label,
        language=language,
    )


def _runner(**kwargs: Any) -> EngineEvaluationRunner:
    """Build a runner writing into a temporary directory."""
    kwargs.setdefault("output_dir", Path("/tmp/opencode/engine_eval_tests"))
    return EngineEvaluationRunner(**kwargs)


def test_unknown_dataset_is_rejected() -> None:
    """Only the corpora with shared loaders are accepted."""
    with pytest.raises(ValueError, match="Unsupported evaluation dataset"):
        _runner(dataset_name="not-a-corpus")


def test_non_positive_batch_size_is_rejected() -> None:
    """A zero batch size would never terminate the batching loop."""
    with pytest.raises(ValueError, match="external_batch_size"):
        _runner(external_batch_size=0)


def test_load_pairs_delegates_to_training_loaders() -> None:
    """Comparison runs must reuse the training pair construction."""
    runner = _runner(dataset_name="conplag")
    expected = [_pair(0, 1), _pair(1, 0)]
    with mock.patch(
        "src.backend.benchmark.runners.learned_fusion_training_runner."
        "LearnedFusionTrainingRunner"
    ) as loader_cls:
        loader_cls.return_value.load_pairs.return_value = expected
        pairs = runner._load_pairs()

    assert pairs == expected
    loader_cls.return_value.load_pairs.assert_called_once_with(["conplag"])


def test_pair_filenames_follow_pair_language() -> None:
    """Python corpora must not be handed to the tools as .java files."""
    assert EngineEvaluationRunner._pair_filenames(_pair(0, 1, "python"), 7) == (
        "pair_0007_a.py",
        "pair_0007_b.py",
    )
    assert EngineEvaluationRunner._pair_filenames(_pair(0, 1, "java"), 3) == (
        "pair_0003_a.java",
        "pair_0003_b.java",
    )


def test_external_tools_are_scored_in_bounded_batches() -> None:
    """JPlag/Dolos are quadratic, so a large pair set must be chunked."""
    pairs = [_pair(index, index % 2) for index in range(7)]
    runner = _runner(external_batch_size=3, enabled_tools=["jplag"])
    calls: list[tuple[str, int]] = []

    def fake_run_tool(
        tool_id: str,
        submissions: dict[str, str],
        pair_tuples: list[tuple[str, str]],
    ) -> dict[str, Any]:
        calls.append((tool_id, len(pair_tuples)))
        return {
            "pairs": [
                {"file_a": file_a, "file_b": file_b, "score": 0.25}
                for file_a, file_b in pair_tuples
            ]
        }

    with mock.patch(
        "src.backend.benchmark.runners.external_tool_runner.ExternalToolRunner"
    ) as runner_cls:
        runner_cls.return_value.run_tool.side_effect = fake_run_tool
        scorers = runner._score_external_tools(pairs)

    assert [size for _, size in calls] == [3, 3, 1]
    assert [scorer.name for scorer in scorers] == ["jplag"]
    scorer = scorers[0]
    assert scorer.available is True
    assert scorer.support == len(pairs)
    assert scorer.scores == [0.25] * len(pairs)


def test_unavailable_tool_is_reported_not_scored() -> None:
    """A tool that cannot run must not be filled with fabricated zeros."""
    pairs = [_pair(index, index % 2) for index in range(4)]
    runner = _runner(enabled_tools=["moss"])
    with mock.patch(
        "src.backend.benchmark.runners.external_tool_runner.ExternalToolRunner"
    ) as runner_cls:
        runner_cls.return_value.run_tool.return_value = None
        scorers = runner._score_external_tools(pairs)

    assert len(scorers) == 1
    assert scorers[0].available is False
    assert "not available" in scorers[0].error
    assert scorers[0].scores == []


def test_failed_batch_disqualifies_the_whole_tool() -> None:
    """Partial tool output would make the AUC depend on batch luck."""
    pairs = [_pair(index, index % 2) for index in range(4)]
    runner = _runner(enabled_tools=["dolos"], external_batch_size=2)
    with mock.patch(
        "src.backend.benchmark.runners.external_tool_runner.ExternalToolRunner"
    ) as runner_cls:
        runner_cls.return_value.run_tool.side_effect = [
            {
                "pairs": [
                    {
                        "file_a": "pair_0000_a.java",
                        "file_b": "pair_0000_b.java",
                        "score": 0.9,
                    },
                    {
                        "file_a": "pair_0001_a.java",
                        "file_b": "pair_0001_b.java",
                        "score": 0.1,
                    },
                ]
            },
            RuntimeError("dolos crashed"),
        ]
        scorers = runner._score_external_tools(pairs)

    assert scorers[0].available is False
    assert "dolos crashed" in scorers[0].error


def test_rule_baseline_is_derived_from_reported_features() -> None:
    """``fused_rule`` must re-apply the production floor to the rule score."""
    pairs = [_pair(0, 1), _pair(1, 0)]
    runner = _runner(enabled_tools=[])

    features = [
        {
            "ast": 0.9,
            "fingerprint": 0.8,
            "embedding": 0.7,
            "ngram": 0.6,
            "winnowing": 0.5,
            "logic_flow": 0.4,
            "fused_score": 0.55,
            "raw_score": 0.91,
            "baseline_adjusted_score": 0.89,
        },
        {
            "ast": 0.2,
            "fingerprint": 0.3,
            "embedding": 0.4,
            "ngram": 0.25,
            "winnowing": 0.15,
            "logic_flow": 0.1,
            "fused_score": 0.22,
            "raw_score": 0.31,
            "baseline_adjusted_score": 0.29,
        },
    ]

    class FakeService:
        """Stand-in for BatchDetectionService with fixed feature rows."""

        def compare_pairs(
            self, submissions: dict[str, str], pairs: list[dict[str, Any]]
        ):
            """Return the canned per-pair feature payloads."""
            results = []
            for index, pair in enumerate(pairs):
                payload = dict(features[index])
                payload.update({"file_a": pair["file_a"], "file_b": pair["file_b"]})
                results.append(
                    mock.Mock(
                        file_a=pair["file_a"], file_b=pair["file_b"], features=payload
                    )
                )
            return results

    from src.backend.application.services.batch_detection_service import (
        _apply_structure_sensitivity_floor,
    )

    with mock.patch(
        "src.backend.application.services.batch_detection_service."
        "BatchDetectionService",
        FakeService,
        create=True,
    ):
        scorers = {
            scorer.name: scorer
            for scorer in runner._score_integritydesk_engines(
                runner._submissions_for_pairs(pairs), pairs
            )
        }

    expected = [
        _apply_structure_sensitivity_floor(0.55, 0.9, 0.8, 0.4, 0.6, 0.5),
        _apply_structure_sensitivity_floor(0.22, 0.2, 0.3, 0.1, 0.25, 0.15),
    ]
    assert scorers["fused_rule"].scores == pytest.approx(expected)
    assert scorers["fused"].scores == pytest.approx([0.91, 0.31])


def test_calibration_metrics_of_a_perfect_score() -> None:
    """Exact probabilities carry zero calibration error."""
    metrics = EngineEvaluationRunner.calibration_metrics(
        [0.0, 1.0, 0.0, 1.0], [0, 1, 0, 1]
    )
    assert metrics["ece"] == pytest.approx(0.0)
    assert metrics["brier"] == pytest.approx(0.0)


def test_calibration_metrics_of_a_confident_wrong_score() -> None:
    """A score of 1.0 on every pair is off by the negative rate."""
    metrics = EngineEvaluationRunner.calibration_metrics([1.0] * 4, [1, 1, 0, 0])
    assert metrics["ece"] == pytest.approx(0.5)
    assert metrics["brier"] == pytest.approx(0.5)


def test_calibration_metrics_handles_no_pairs() -> None:
    """An unavailable tool has nothing to calibrate."""
    assert EngineEvaluationRunner.calibration_metrics([], []) == {
        "ece": 0.0,
        "brier": 0.0,
    }


def test_report_without_calibration_fields_still_loads(tmp_path) -> None:
    """Reports written before ECE/Brier existed must stay readable."""
    path = tmp_path / "old.json"
    path.write_text(
        '{"run_id": "R", "timestamp": "t", "dataset_name": "d", "language": "java",'
        ' "pair_count": 1, "positive_pairs": 1, "negative_pairs": 0,'
        ' "runtime_seconds": 0.1, "scorers": [{"name": "fused", "kind": "integritydesk",'
        ' "available": true, "support": 1, "auc_roc": 0.5}]}'
    )
    report = module_report().from_json(path)
    assert report.scorers[0].ece == 0.0
    assert report.scorers[0].brier == 0.0


def module_report():
    """Return the report class used by the harness."""
    from src.backend.benchmark.runners.engine_evaluation_runner import (
        EngineEvaluationReport,
    )

    return EngineEvaluationReport
