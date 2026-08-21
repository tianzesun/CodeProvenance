"""Unit tests for the learned fusion training runner helpers."""

import json
from pathlib import Path

from src.backend.benchmark.runners.learned_fusion_training_runner import (
    LearnedFusionTrainingRunner,
)


class TestNormalizePair:
    """Order-independent pair key normalization."""

    def test_sorts_files(self):
        """Pair keys are normalized by sorted file names."""
        assert LearnedFusionTrainingRunner._normalize_pair("b.java", "a.java") == (
            "a.java",
            "b.java",
        )

    def test_idempotent(self):
        """Normalization is order independent and stable."""
        key = LearnedFusionTrainingRunner._normalize_pair("a.java", "b.java")
        assert LearnedFusionTrainingRunner._normalize_pair("a.java", "b.java") == key


class TestAuc:
    """ROC-AUC concordance estimator."""

    def test_perfect_separation(self):
        """Perfectly separated scores yield AUC 1.0."""
        auc = LearnedFusionTrainingRunner._auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0])
        assert auc == 1.0

    def test_requires_both_classes(self):
        """AUC requires both classes present in labels."""
        assert LearnedFusionTrainingRunner._auc([0.9, 0.8], [1, 1]) == 0.0


class TestBestThreshold:
    """Best-F1 threshold sweep."""

    def test_picks_perfect_split(self):
        """Threshold sweep finds the perfect F1 split."""
        best = LearnedFusionTrainingRunner(
            output_dir=Path("/tmp/unused")
        )._best_threshold([0.9, 0.85, 0.2, 0.1], [1, 1, 0, 0])
        assert best["f1"] == 1.0
        assert best["threshold"] <= 0.9

    def test_metrics_at_threshold(self):
        """Precision/recall/F1 computed at a cutoff."""
        metrics = LearnedFusionTrainingRunner._metrics_at_threshold(
            [0.9, 0.4, 0.6, 0.1], [1, 1, 0, 0], 0.5
        )
        assert metrics["precision"] == 0.5
        assert metrics["recall"] == 0.5
        assert metrics["f1"] == 0.5


class TestReportSerialization:
    """Report JSON round-trip includes learned coefficients."""

    def _report(self):
        """Build a representative report instance for serialization tests."""
        from src.backend.benchmark.runners.learned_fusion_training_runner import (
            LearnedFusionReport,
        )

        return LearnedFusionReport(
            generated_at="2026-01-01T00:00:00",
            train_datasets=["IR-Plag-Dataset", "conplag"],
            pair_count=2,
            positive_pairs=1,
            negative_pairs=1,
            feature_names=[
                "ast",
                "fingerprint",
                "embedding",
                "ngram",
                "winnowing",
                "logic_flow",
                "coverage",
            ],
            production_fused_auc=0.7,
            production_fused_f1_best=0.6,
            production_fused_threshold=0.2,
            logo_auc=0.9,
            logo_f1_best=0.8,
            logo_threshold=0.4,
            logo_fold_count=2,
            coefficient_weights={"ast": -2.5, "winnowing": 4.2},
            intercept=-2.0,
            artifact_path="/tmp/model.json",
        )

    def test_to_json_dict(self):
        """Report serializes learned coefficients and metadata."""
        report = self._report()
        payload = report.to_json_dict()
        assert payload["feature_names"] == [
            "ast",
            "fingerprint",
            "embedding",
            "ngram",
            "winnowing",
            "logic_flow",
            "coverage",
        ]
        assert payload["coefficient_weights"].get("ast") is not None

    def test_save_json(self, tmp_path):
        """Report persists to a JSON file."""
        report = self._report()
        path = report.save_json(tmp_path / "report.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["pair_count"] == 2
        assert payload["logo_auc"] == 0.9
