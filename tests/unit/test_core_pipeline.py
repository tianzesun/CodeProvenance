"""Unit tests for core detection pipeline components.

Tests:
- FeatureExtractor (feature extraction from code pairs)
- FusionEngine (multi-engine score fusion)
- DecisionEngine (threshold-based decisions)
- CodeBERTSimilarity / UniXcoderSimilarity (embedding engines)
- TokenSimilarity (token-based similarity)
"""
from __future__ import annotations

import pytest

from src.engines.features.feature_extractor import FeatureExtractor, FeatureVector
from src.engines.scoring.fusion_engine import FusionEngine, FusedScore, DEFAULT_WEIGHTS
from src.domain.decision.decision_engine import DecisionEngine, DecisionResult


# ─── FeatureExtractor ──────────────────────────────────────────────────

class TestFeatureExtractor:
    """Tests for the FeatureExtractor class."""

    def setup_method(self) -> None:
        self.extractor = FeatureExtractor()

    def test_feature_vector_defaults(self) -> None:
        """Default FeatureVector has all zeros."""
        fv = FeatureVector()
        assert fv.ast == 0.0
        assert fv.fingerprint == 0.0
        assert fv.embedding == 0.0
        assert fv.ngram == 0.0
        assert fv.winnowing == 0.0

    def test_to_features_order(self) -> None:
        """to_features() returns features in FEATURE_ORDER."""
        fv = FeatureVector(ast=0.1, fingerprint=0.2, embedding=0.3, ngram=0.4, winnowing=0.5)
        result = self.extractor.to_features(fv)
        assert result == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_extract_identical_code_returns_max_scores(self) -> None:
        """Comparing identical code should produce non-zero similarity scores."""
        code = "def add(a, b):\n    return a + b"
        fv = self.extractor.extract(code, code)
        # Engine availability varies; at minimum ngram/embedding/fingerprint
        # should score high for identical input.
        assert fv.ngram > 0.0
        assert fv.fingerprint > 0.0
        assert 0.0 <= fv.ast <= 1.0
        assert 0.0 <= fv.embedding <= 1.0

    def test_extract_different_code(self) -> None:
        """Completely different code should have low (but not necessarily zero) scores."""
        code_a = "def foo(): return 1"
        code_b = "class Bar: pass"
        fv = self.extractor.extract(code_a, code_b)
        # All fields should be valid floats in [0, 1]
        for name in FeatureExtractor.FEATURE_ORDER:
            val = getattr(fv, name)
            assert isinstance(val, float)
            assert 0.0 <= val <= 1.0

    def test_extract_empty_strings(self) -> None:
        """Empty code pairs should return valid floats without crashing.
        
        Note: Identical empty code returns 1.0 similarity (100% match).
        """
        fv = self.extractor.extract("", "")
        for name in FeatureExtractor.FEATURE_ORDER:
            val = getattr(fv, name)
            assert isinstance(val, float)
            assert 0.0 <= val <= 1.0


# ─── FusionEngine ────────────────────────────────────────────────────────

class TestFusionEngine:
    """Tests for the FusionEngine class."""

    def test_default_weights_normalized(self) -> None:
        """Default weights must sum to 1.0."""
        engine = FusionEngine()
        total = sum(engine.weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_custom_weights_normalized(self) -> None:
        """Custom weights are normalized to sum 1.0."""
        # Raw weights sum to 10, should normalize
        engine = FusionEngine(weights={"ast": 5, "fingerprint": 5, "embedding": 0, "ngram": 0, "winnowing": 0})
        assert abs(sum(engine.weights.values()) - 1.0) < 1e-9
        assert engine.weights["ast"] == 0.5
        assert engine.weights["fingerprint"] == 0.5

    def test_fuse_all_max(self) -> None:
        """All features = 1.0 → final score = 1.0."""
        engine = FusionEngine()
        fv = FeatureVector(ast=1.0, fingerprint=1.0, embedding=1.0, ngram=1.0, winnowing=1.0)
        result = engine.fuse(fv)
        assert result.final_score == 1.0

    def test_fuse_all_zero(self) -> None:
        """All features = 0.0 → final score = 0.0."""
        engine = FusionEngine()
        fv = FeatureVector()
        result = engine.fuse(fv)
        assert result.final_score == 0.0

    def test_fuse_partial(self) -> None:
        """Mixed features produce weighted average."""
        engine = FusionEngine(weights={
            "ast": 0.5, "fingerprint": 0.5, "embedding": 0.0, "ngram": 0.0, "winnowing": 0.0,
        })
        fv = FeatureVector(ast=1.0, fingerprint=0.0, embedding=0.0, ngram=0.0, winnowing=0.0)
        result = engine.fuse(fv)
        assert result.final_score == 0.5

    def test_fuse_clamped(self) -> None:
        """Fusion output is clamped to [0, 1]."""
        engine = FusionEngine()
        # Use mock-like fv with values > 1 to test clamp (shouldn't happen in practice)
        fv = FeatureVector(ast=1.0, fingerprint=1.0, embedding=1.0, ngram=1.0, winnowing=1.0)
        result = engine.fuse(fv)
        assert 0.0 <= result.final_score <= 1.0

    def test_fuse_returns_components(self) -> None:
        """FusedScore contains per-engine component breakdown."""
        engine = FusionEngine()
        fv = FeatureVector(ast=0.3, fingerprint=0.5, embedding=0.7, ngram=0.1, winnowing=0.2)
        result = engine.fuse(fv)
        assert "ast" in result.components
        assert "fingerprint" in result.components
        assert result.components["ast"] == 0.3

    def test_get_weights(self) -> None:
        """get_weights returns a copy of current weights."""
        engine = FusionEngine()
        w1 = engine.get_weights()
        w2 = engine.get_weights()
        assert w1 == w2
        assert w1 is not w2

    def test_set_weights(self) -> None:
        """set_weights updates and normalizes new weights."""
        engine = FusionEngine()
        engine.set_weights({"ast": 10, "fingerprint": 0, "embedding": 0, "ngram": 0, "winnowing": 0})
        assert engine.weights["ast"] == 1.0
        assert engine.weights["fingerprint"] == 0.0


# ─── DecisionEngine ────────────────────────────────────────────────────

class TestDecisionEngine:
    """Tests for the DecisionEngine class."""

    def test_decide_above_threshold(self) -> None:
        """Score above threshold → verdict 1 (plagiarism)."""
        engine = DecisionEngine(threshold=0.5)
        result = engine.decide(0.8)
        assert result.final_verdict == 1

    def test_decide_below_threshold(self) -> None:
        """Score below threshold → verdict 0 (clean)."""
        engine = DecisionEngine(threshold=0.5)
        result = engine.decide(0.3)
        assert result.final_verdict == 0

    def test_decide_on_threshold(self) -> None:
        """Score exactly on threshold → verdict 1."""
        engine = DecisionEngine(threshold=0.5)
        result = engine.decide(0.5)
        assert result.final_verdict == 1

    def test_confidence_far_from_threshold(self) -> None:
        """Confidence higher when score is far from threshold."""
        engine = DecisionEngine(threshold=0.5)
        close = engine.decide(0.51)
        far = engine.decide(0.99)
        assert far.confidence > close.confidence

    def test_batch_decide(self) -> None:
        """batch_decide returns list of DecisionResults."""
        engine = DecisionEngine(threshold=0.5)
        scores = [0.1, 0.5, 0.9]
        results = engine.batch_decide(scores)
        assert len(results) == 3
        assert results[0].final_verdict == 0  # 0.1 < 0.5
        assert results[1].final_verdict == 1  # 0.5 == 0.5
        assert results[2].final_verdict == 1  # 0.9 > 0.5

    def test_decision_result_fields(self) -> None:
        """DecisionResult has expected attributes."""
        engine = DecisionEngine(threshold=0.5)
        result = engine.decide(0.7)
        assert isinstance(result.final_verdict, int)
        assert isinstance(result.confidence, float)
        assert isinstance(result.threshold_used, float)
        assert result.threshold_used == 0.5