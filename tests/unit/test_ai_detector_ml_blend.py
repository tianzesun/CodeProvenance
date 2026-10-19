"""Unit tests for the orchestrator safe-blend fusion and FP safeguards."""

from src.backend.engines.ai.orchestrator import (
    AIDetectionOrchestrator,
    apply_fp_safeguards,
    blend_ml_heuristic,
)


class TestBlendMLHeuristic:
    """blend_ml_heuristic: length-gated, disagreement-capped classifier blend."""

    def test_short_file_damps_classifier_weight(self) -> None:
        # 10 lines -> length factor 0.2 -> classifier weight 0.10.
        score, capped = blend_ml_heuristic(0.95, 0.20, 10)
        assert not capped
        assert score < 0.30  # dominated by the heuristic score

    def test_long_file_gives_classifier_full_weight(self) -> None:
        # 60+ lines -> weight 0.50: an even blend of both scores.
        score, capped = blend_ml_heuristic(0.90, 0.20, 80)
        assert not capped
        assert abs(score - 0.55) < 1e-9

    def test_length_interpolation_is_monotonic(self) -> None:
        short = blend_ml_heuristic(0.9, 0.1, 26)[0]
        mid = blend_ml_heuristic(0.9, 0.1, 40)[0]
        full = blend_ml_heuristic(0.9, 0.1, 60)[0]
        assert short < mid < full

    def test_disagreement_caps_false_positive_direction(self) -> None:
        # Classifier says AI (1.0), heuristics are neutral (0.5), long file:
        # the uncapped blend (0.75) must be capped below high risk.
        score, capped = blend_ml_heuristic(1.0, 0.5, 80)
        assert capped
        assert score == 0.65

    def test_cap_only_binds_above_the_cap_value(self) -> None:
        # A strong disagreement whose blend already sits below the cap is
        # left untouched (the length gate has already contained it).
        score, capped = blend_ml_heuristic(0.95, 0.20, 80)
        assert not capped
        assert score == 0.575

    def test_reverse_disagreement_is_never_capped(self) -> None:
        # Heuristics say AI (fingerprints fired), classifier says human.
        score, capped = blend_ml_heuristic(0.10, 0.90, 80)
        assert not capped
        assert score == 0.50

    def test_config_overrides_defaults(self) -> None:
        score, capped = blend_ml_heuristic(0.95, 0.20, 80, {"ml_base_weight": 0.0})
        assert not capped
        assert score == 0.20

    def test_classifier_only_conviction_is_held_out_of_the_review_band(self) -> None:
        # Measured 2026-10-18 on 174 Kaggle student submissions: the classifier
        # lifted 20.1% of real human files over 0.40 versus 9.2% without it
        # (unchanged at 0.70). With the guard enabled, a confident classifier
        # call that no explainable signal corroborates (heuristic 0.20) is held
        # at 0.35 instead of the 0.575 the length gate alone allows.
        conf = {"corroboration_floor": 0.30, "classifier_only_cap": 0.35}
        score, capped = blend_ml_heuristic(0.95, 0.20, 80, conf)
        assert capped
        assert score == 0.35

    def test_corroborated_classifier_call_keeps_its_full_cap(self) -> None:
        # Heuristic 0.45 is above the corroboration floor (the explainable
        # signals carry evidence), so the guard must not fire.
        conf = {"corroboration_floor": 0.30, "classifier_only_cap": 0.35}
        score, capped = blend_ml_heuristic(0.80, 0.45, 80, conf)
        assert not capped
        assert score == 0.625

    def test_guard_is_disabled_by_default(self) -> None:
        # Shipped default keeps the previous behaviour until an operator opts in.
        score, capped = blend_ml_heuristic(0.95, 0.20, 80)
        assert not capped
        assert score == 0.575


class TestApplyFPSafeguards:
    """apply_fp_safeguards: ported framework penalties on the live path."""

    def test_clean_signals_leave_scores_unchanged(self) -> None:
        signals = {name: 0.2 for name in range(8)}
        probability, confidence, notes = apply_fp_safeguards(0.25, 0.7, signals)
        assert probability == 0.25
        assert confidence == 0.7
        assert notes == []

    def test_single_signal_dominance_reduces_confidence(self) -> None:
        # One signal mildly AI-like (0.65), the rest mildly human-like (0.35):
        # dominance fires without contradiction or variance.
        signals = {name: 0.35 for name in range(8)}
        signals[3] = 0.65
        _, confidence, notes = apply_fp_safeguards(0.5, 0.7, signals)
        assert confidence == 0.4
        assert any("dominance" in note for note in notes)

    def test_contradiction_reduces_confidence(self) -> None:
        signals = {name: 0.5 for name in range(8)}
        signals[0] = 0.8
        signals[1] = 0.2
        _, confidence, notes = apply_fp_safeguards(0.5, 0.7, signals)
        assert confidence == 0.5
        assert any("contradiction" in note for note in notes)

    def test_extreme_variance_reduces_confidence(self) -> None:
        # Four 0.0s and four 0.65s: variance 0.106 > 0.10, but no value pair
        # crosses the contradiction bounds (>0.7 vs <0.3).
        signals = {name: (0.65 if name < 4 else 0.0) for name in range(8)}
        _, confidence, notes = apply_fp_safeguards(0.7, 0.7, signals)
        assert confidence == 0.55
        assert any("variance" in note for note in notes)

    def test_low_confidence_high_score_is_capped_below_high_band(self) -> None:
        # Recalibrated 2026-09-21: a 0.9 score with near-zero confidence used
        # to be damped to 0.82 — still a red high-band flag. Uncertain calls
        # must now cap just below the high-risk threshold instead.
        signals = {name: 0.2 for name in range(8)}
        signals[3] = 0.8
        probability, _, notes = apply_fp_safeguards(0.9, 0.1, signals)
        assert probability == 0.66
        assert any("damped" in note for note in notes)

    def test_low_confidence_moderate_score_damps_toward_neutral(self) -> None:
        # Scores below the high band keep the original gentle damper.
        signals = {name: 0.2 for name in range(8)}
        signals[3] = 0.8
        probability, _, notes = apply_fp_safeguards(0.3, 0.1, signals)
        assert probability == round(0.3 * 0.8 + 0.1, 3)
        assert any("damped" in note for note in notes)

    def test_few_signals_skip_safeguards(self) -> None:
        _, confidence, notes = apply_fp_safeguards(0.9, 0.7, {"a": 1.0, "b": 0.0})
        assert confidence == 0.7
        assert notes == []


class TestOrchestratorSafeBlendIntegration:
    """The orchestrator must expose the blend, not trust the classifier."""

    def test_disagreeing_classifier_is_capped_and_flagged(self, monkeypatch) -> None:
        long_code = "\n".join(
            f"value_{index} = compute_{index}(total_{index})" for index in range(80)
        )

        def fake_score(self, code, language="python", pattern_library=None):
            return {
                "ai_probability": 0.95,
                "method": "ensemble",
                "mode": "ml",
                "signals": {"ast": 0.2, "stylometry": 0.2},
                "flagged_regions": [],
                "classifier": {"ai_probability": 0.95, "version": "test"},
            }

        monkeypatch.setattr(
            "src.backend.engines.ai.ensemble.AIEnsembleScorer.score", fake_score
        )
        # Mid-band heuristic + extreme classifier on a long file lands in the
        # cap region (0.5 * 0.95 + 0.5 * 0.45 = 0.70 > 0.65).
        monkeypatch.setattr(
            AIDetectionOrchestrator, "_heuristic_fuse", lambda self, signals: 0.45
        )
        result = AIDetectionOrchestrator().analyze(long_code, language="python")

        fusion = result["layers"]["fusion"]
        assert fusion["strategy"] == "ml_blend"
        assert fusion["disagreement_capped"] is True
        assert result["ai_probability"] <= 0.65
        assert result["method"] == "ml"
        assert any("disagreement" in indicator for indicator in result["indicators"])

    def test_classifier_only_conviction_is_held_below_the_review_band(
        self, monkeypatch
    ) -> None:
        long_code = "\n".join(
            f"value_{index} = compute_{index}(total_{index})" for index in range(80)
        )

        def fake_score(self, code, language="python", pattern_library=None):
            return {
                "ai_probability": 0.95,
                "method": "ensemble",
                "mode": "ml",
                "signals": {"ast": 0.2, "stylometry": 0.2},
                "flagged_regions": [],
                "classifier": {"ai_probability": 0.95, "version": "test"},
            }

        monkeypatch.setattr(
            "src.backend.engines.ai.ensemble.AIEnsembleScorer.score", fake_score
        )
        monkeypatch.setattr(
            AIDetectionOrchestrator, "_heuristic_fuse", lambda self, signals: 0.20
        )
        monkeypatch.setattr(
            AIDetectionOrchestrator,
            "_blend_config",
            lambda self: {"corroboration_floor": 0.30, "classifier_only_cap": 0.35},
        )
        result = AIDetectionOrchestrator().analyze(long_code, language="python")

        assert result["method"] == "ml"
        assert result["layers"]["fusion"]["disagreement_capped"] is True
        # The low-confidence damper contracts 0.35 toward the middle (0.38), but
        # the invariant the guard exists for is that an unevidenced classifier
        # call stays out of the review band.
        assert result["ai_probability"] < 0.40

    def test_agreeing_classifier_raises_score_without_cap(self, monkeypatch) -> None:
        from tests.unit.test_ai_detector_orchestrator_precision import AI_CANONICAL

        def fake_score(self, code, language="python", pattern_library=None):
            return {
                "ai_probability": 0.80,
                "method": "ensemble",
                "mode": "ml",
                "signals": {"ast": 0.6, "stylometry": 0.7},
                "flagged_regions": [],
                "classifier": {"ai_probability": 0.80, "version": "test"},
            }

        monkeypatch.setattr(
            "src.backend.engines.ai.ensemble.AIEnsembleScorer.score", fake_score
        )
        result = AIDetectionOrchestrator().analyze(AI_CANONICAL, language="python")

        fusion = result["layers"]["fusion"]
        assert fusion["disagreement_capped"] is False
        assert result["ai_probability"] >= 0.60
