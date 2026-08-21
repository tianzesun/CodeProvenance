"""Unit tests for the learned fusion scoring model."""

import json
from pathlib import Path

import pytest

from src.backend.engines.scoring.learned_fusion import (
    ARTIFACT_VERSION,
    LearnedFusionScorer,
)


def _write_artifact(path: Path, coefficients, intercept=0.0, features=None):
    """Write a minimal valid artifact JSON for scorer tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": ARTIFACT_VERSION,
        "feature_names": features
        or [
            "ast",
            "fingerprint",
            "embedding",
            "ngram",
            "winnowing",
            "logic_flow",
            "coverage",
        ],
        "coefficients": coefficients,
        "intercept": intercept,
        "metadata": {"trained_at": "2026-01-01T00:00:00", "datasets": ["irplag"]},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestLearnedFusionScorer:
    """Tests for the JSON-artifact fusion scorer."""

    def test_unavailable_when_no_artifact(self, tmp_path):
        """Score returns 0.0 and available is False when artifact is missing."""
        scorer = LearnedFusionScorer(artifact_path=tmp_path / "missing.json")
        assert scorer.available is False
        assert scorer.score({}) == pytest.approx(0.0)

    def test_corrupt_artifact_falls_back(self, tmp_path):
        """Invalid JSON makes the scorer unavailable instead of raising."""
        path = tmp_path / "model.json"
        path.write_text("{not valid json", encoding="utf-8")
        scorer = LearnedFusionScorer(artifact_path=path)
        assert scorer.available is False

    def test_mismatched_lengths_rejected(self, tmp_path):
        """Feature/coefficient count mismatch invalidates the artifact."""
        path = _write_artifact(tmp_path / "model.json", coefficients=[0.5, 0.5])
        scorer = LearnedFusionScorer(artifact_path=path)
        assert scorer.available is False

    def test_wrong_version_rejected(self, tmp_path):
        """Unsupported artifact versions are rejected."""
        path = tmp_path / "model.json"
        path.write_text(
            json.dumps(
                {
                    "version": "99",
                    "feature_names": ["ast"],
                    "coefficients": [1.0],
                    "intercept": 0.0,
                }
            ),
            encoding="utf-8",
        )
        scorer = LearnedFusionScorer(artifact_path=path)
        assert scorer.available is False

    def test_positive_features_score_above_intercept(self, tmp_path):
        """Strong positive features pull the score above baseline."""
        path = _write_artifact(
            tmp_path / "model.json",
            coefficients=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            intercept=-3.0,
        )
        scorer = LearnedFusionScorer(artifact_path=path)
        assert scorer.available is True
        low = scorer.score({"ast": 0.1, "fingerprint": 0.1})
        high = scorer.score({"ast": 0.9, "fingerprint": 0.9, "coverage": 0.9})
        assert high > low
        assert 0.0 <= high <= 1.0

    def test_missing_features_treated_as_zero(self, tmp_path):
        """Missing features degrade to 0.0 like an explicit zero."""
        path = _write_artifact(
            tmp_path / "model.json",
            coefficients=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            intercept=-3.0,
        )
        scorer = LearnedFusionScorer(artifact_path=path)
        empty = scorer.score({})
        known_neg = scorer.score(
            {
                "ast": 0.0,
                "fingerprint": 0.0,
                "embedding": 0.0,
                "ngram": 0.0,
                "winnowing": 0.0,
                "logic_flow": 0.0,
                "coverage": 0.0,
            }
        )
        assert empty == pytest.approx(known_neg)

    def test_metadata_exposed(self, tmp_path):
        """Training metadata is surfaced via version_info."""
        path = _write_artifact(
            tmp_path / "model.json",
            coefficients=[1.0],
            features=["ast"],
        )
        scorer = LearnedFusionScorer(artifact_path=path)
        assert scorer.version_info()["datasets"] == ["irplag"]

    def test_large_logits_clamped(self, tmp_path):
        """Large logits are clamped into the [0, 1] probability range."""
        path = _write_artifact(
            tmp_path / "model.json",
            coefficients=[50.0],
            features=["ast"],
        )
        scorer = LearnedFusionScorer(artifact_path=path)
        score = scorer.score({"ast": 1.0})
        assert score == pytest.approx(1.0)
        assert 0.0 <= score <= 1.0

    def test_negative_weights_pull_score_down(self, tmp_path):
        """Negative coefficients drive the probability below 0.5."""
        path = _write_artifact(
            tmp_path / "model.json",
            coefficients=[-5.0, -5.0, -5.0, -5.0, -5.0, -5.0, -5.0],
            intercept=1.0,
        )
        scorer = LearnedFusionScorer(artifact_path=path)
        score = scorer.score({"ast": 0.9, "fingerprint": 0.9, "coverage": 0.9})
        assert score < 0.5
        assert 0.0 <= score <= 1.0
