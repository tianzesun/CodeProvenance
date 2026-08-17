"""Unit tests for the engine evaluation harness metrics."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.backend.benchmark.runners.engine_evaluation_runner import (
    EngineEvaluationRunner,
    LabeledPair,
    ScorerResult,
)


@dataclass
class _FakeComparisonResult:
    """Minimal stand-in for BatchDetectionService.ComparisonResult."""

    file_a: str
    file_b: str
    features: dict


class TestMetricsAtThreshold:
    """Tests for the threshold metrics helper."""

    def test_perfect_score_separation(self):
        scores = [0.9, 0.85, 0.2, 0.1]
        labels = [1, 1, 0, 0]
        metrics = EngineEvaluationRunner.metrics_at_threshold(scores, labels, 0.5)
        assert metrics["tp"] == 2
        assert metrics["fp"] == 0
        assert metrics["tn"] == 2
        assert metrics["fn"] == 0
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0

    def test_false_positive_at_low_threshold(self):
        scores = [0.2, 0.8, 0.6, 0.1]
        labels = [1, 1, 0, 0]
        metrics = EngineEvaluationRunner.metrics_at_threshold(scores, labels, 0.5)
        # 0.8 positive, 0.6 is FP, 0.2 positive is FN
        assert metrics["tp"] == 1
        assert metrics["fp"] == 1
        assert metrics["fn"] == 1
        assert metrics["tn"] == 1
        assert metrics["precision"] == pytest.approx(0.5)
        assert metrics["recall"] == pytest.approx(0.5)

    def test_empty_positives_zero_recall(self):
        metrics = EngineEvaluationRunner.metrics_at_threshold([0.9, 0.1], [0, 0], 0.5)
        assert metrics["tp"] == 0
        assert metrics["recall"] == 0.0
        assert metrics["precision"] == 0.0


class TestAucRoc:
    """Tests for the rank-free AUC estimator."""

    def test_perfect_auc_is_one(self):
        scores = [0.9, 0.8, 0.2, 0.1]
        labels = [1, 1, 0, 0]
        assert EngineEvaluationRunner.auc_roc(scores, labels) == pytest.approx(1.0)

    def test_random_auc_is_half(self):
        scores = [0.6, 0.4, 0.7, 0.3]
        labels = [1, 0, 0, 1]
        # positive scores: 0.6, 0.3 ; negative: 0.4, 0.7
        # concordant pairs: 0.6>0.4 yes, 0.6>0.7 no, 0.3>0.4 no, 0.3>0.7 no
        auc = EngineEvaluationRunner.auc_roc(scores, labels)
        assert auc == pytest.approx(0.25)

    def test_auc_handles_tied_scores(self):
        scores = [0.5, 0.5, 0.5, 0.5]
        labels = [1, 1, 0, 0]
        assert EngineEvaluationRunner.auc_roc(scores, labels) == pytest.approx(0.5)

    def test_auc_requires_both_classes(self):
        assert EngineEvaluationRunner.auc_roc([0.9, 0.8], [1, 1]) == 0.0
        assert EngineEvaluationRunner.auc_roc([0.9, 0.8], [0, 0]) == 0.0


class TestBestThreshold:
    """Tests for the best-threshold sweep."""

    def test_picks_threshold_with_highest_f1(self):
        scores = [0.9, 0.85, 0.55, 0.1]
        labels = [1, 1, 0, 0]
        best = EngineEvaluationRunner.best_threshold_metrics(scores, labels, 0.02)
        # threshold 0.7-0.9 buckets separate perfectly
        assert best["f1"] == pytest.approx(1.0)
        assert best["threshold"] <= 0.9

    def test_step_bounded(self):
        scores = [0.9, 0.8, 0.2, 0.1]
        labels = [1, 1, 0, 0]
        best = EngineEvaluationRunner.best_threshold_metrics(scores, labels, 0.02)
        assert best["threshold"] >= 0.02


class TestScorerResultJson:
    """Tests for the JSON round-trip of scorer results."""

    def test_to_json_dict_shapes(self):
        scorer = ScorerResult(
            name="ast",
            kind="integritydesk",
            available=True,
            support=4,
            auc_roc=0.75,
            scores=[0.5, 0.6, 0.7, 0.8],
            labels=[0, 1, 0, 1],
        )
        payload = scorer.to_json_dict()
        assert payload["name"] == "ast"
        assert payload["scores"] == [0.5, 0.6, 0.7, 0.8]
        assert payload["auc_roc"] == 0.75

    def test_unavailable_scorer(self):
        scorer = EngineEvaluationRunner._unavailable_scorer("moss", "no user id")
        assert scorer.available is False
        assert scorer.error == "no user id"
        assert scorer.kind == "external_tool"


class TestPairAlignment:
    """Tests that scores align to labels via filenames, not result order."""

    def test_scores_aligned_by_filename_when_results_sorted(self, monkeypatch):
        pairs = [
            LabeledPair(pair_id="p0", code_a="a", code_b="b", label=0),
            LabeledPair(pair_id="p1", code_a="c", code_b="d", label=1),
        ]
        runner = EngineEvaluationRunner(
            output_dir=Path("/tmp/engine_eval_test"), dataset_root=Path("/nonexistent")
        )

        # compare_pairs sorts by score descending; the highest-scoring pair
        # (p1, label 1) returns first even though it was asked second.
        fake_results = [
            _FakeComparisonResult(
                file_a="pair_0001_a.java",
                file_b="pair_0001_b.java",
                features={
                    "ast": 0.9,
                    "fingerprint": 0.9,
                    "ngram": 0.9,
                    "winnowing": 0.9,
                    "embedding": 0.9,
                    "logic_flow": 0.9,
                    "raw_score": 0.9,
                    "fused_score": 0.95,
                    "baseline_adjusted_score": 0.85,
                },
            ),
            _FakeComparisonResult(
                file_a="pair_0000_a.java",
                file_b="pair_0000_b.java",
                features={
                    "ast": 0.1,
                    "fingerprint": 0.1,
                    "ngram": 0.1,
                    "winnowing": 0.1,
                    "embedding": 0.1,
                    "logic_flow": 0.1,
                    "raw_score": 0.1,
                    "fused_score": 0.05,
                    "baseline_adjusted_score": 0.15,
                },
            ),
        ]

        class _FakeService:
            def compare_pairs(self, submissions=None, pairs=None):
                return fake_results

        import src.backend.application.services.batch_detection_service as svc

        monkeypatch.setattr(svc, "BatchDetectionService", _FakeService)

        submissions = runner._submissions_for_pairs(pairs)
        scorers = runner._score_integritydesk_engines(submissions, pairs)

        ast = next(s for s in scorers if s.name == "ast")
        assert ast.labels == [0, 1]
        assert ast.scores == [0.1, 0.9]
        assert ast.auc_roc == pytest.approx(1.0)

        fused = next(s for s in scorers if s.name == "fused")
        assert fused.kind == runner.SCORER_KIND_INTEGRITYDESK
        assert fused.scores == [0.1, 0.9]

        prescore = next(s for s in scorers if s.name == "fused_score")
        assert prescore.scores == [0.05, 0.95]
        assert prescore.auc_roc == pytest.approx(1.0)

        adjusted = next(s for s in scorers if s.name == "baseline_adjusted_score")
        assert adjusted.scores == [0.15, 0.85]
        assert fused.scores == [0.1, 0.9]
