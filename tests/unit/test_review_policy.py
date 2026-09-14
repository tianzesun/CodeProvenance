"""Unit tests for src/backend/engines/scoring/review_policy.py.

Covers:
- compute_band: correct band for each mode at boundary values
- compute_band: score clamping, unknown modes, override config
- compute_corroboration: all five rules
- compute_corroboration: edge cases (boundary AI scores, empty engine scores)
- allowed_dispositions_for_pair: combined band + corroboration constraints
- validate_disposition: acceptance and rejection paths
"""

import pytest

from src.backend.engines.scoring.review_policy import (
    BAND_THRESHOLDS,
    HIGH_STAKES_DISPOSITIONS,
    BandThresholdConfig,
    CorroborationResult,
    allowed_dispositions_for_pair,
    compute_band,
    compute_corroboration,
    get_thresholds,
    validate_disposition,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def algo_cfg() -> BandThresholdConfig:
    """Algorithms mode thresholds (review=0.35, high=0.65)."""
    return BandThresholdConfig.from_dict(BAND_THRESHOLDS["algorithms"])


@pytest.fixture
def intro_cfg() -> BandThresholdConfig:
    """Introductory mode thresholds (review=0.45, high=0.70)."""
    return BandThresholdConfig.from_dict(BAND_THRESHOLDS["introductory"])


@pytest.fixture
def custom_cfg() -> BandThresholdConfig:
    """Custom override config for isolation tests."""
    return BandThresholdConfig(
        review_min=0.40,
        high_min=0.70,
        ai_elevated_min=0.65,
        web_match_min=0.70,
        engine_agree_count=2,
        engine_agree_min=0.50,
    )


# ---------------------------------------------------------------------------
# get_thresholds
# ---------------------------------------------------------------------------


class TestGetThresholds:
    """get_thresholds: lookup order and fallback behaviour."""

    def test_known_mode_returned(self):
        cfg = get_thresholds("algorithms")
        assert cfg.review_min == 0.35
        assert cfg.high_min == 0.65

    def test_mode_is_case_insensitive(self):
        cfg = get_thresholds("ALGORITHMS")
        assert cfg.review_min == 0.35

    def test_none_falls_through_to_default(self):
        cfg = get_thresholds(None)
        assert cfg.review_min == BAND_THRESHOLDS["default"]["review_min"]

    def test_empty_string_falls_through_to_default(self):
        cfg = get_thresholds("")
        assert cfg.review_min == BAND_THRESHOLDS["default"]["review_min"]

    def test_unknown_mode_falls_through_to_default(self):
        cfg = get_thresholds("totally_unknown_mode")
        assert cfg.review_min == BAND_THRESHOLDS["default"]["review_min"]

    def test_override_wins_over_lookup(self, custom_cfg):
        cfg = get_thresholds("algorithms", override=custom_cfg)
        assert cfg.review_min == 0.40  # custom, not 0.35


# ---------------------------------------------------------------------------
# compute_band — band classification
# ---------------------------------------------------------------------------


class TestComputeBand:
    """compute_band: correct band at and around boundary values."""

    # --- algorithms mode (review=0.35, high=0.65) ---

    def test_below_review_is_low(self, algo_cfg):
        r = compute_band(0.34, threshold_override=algo_cfg)
        assert r.band == "low"

    def test_exactly_at_review_min_is_review(self, algo_cfg):
        r = compute_band(0.35, threshold_override=algo_cfg)
        assert r.band == "review"

    def test_inside_review_band_is_review(self, algo_cfg):
        r = compute_band(0.50, threshold_override=algo_cfg)
        assert r.band == "review"

    def test_just_below_high_is_review(self, algo_cfg):
        r = compute_band(0.649, threshold_override=algo_cfg)
        assert r.band == "review"

    def test_exactly_at_high_min_is_high(self, algo_cfg):
        r = compute_band(0.65, threshold_override=algo_cfg)
        assert r.band == "high"

    def test_well_above_high_min_is_high(self, algo_cfg):
        r = compute_band(0.99, threshold_override=algo_cfg)
        assert r.band == "high"

    # --- introductory mode (review=0.45, high=0.70) ---

    def test_intro_low(self, intro_cfg):
        assert compute_band(0.44, threshold_override=intro_cfg).band == "low"

    def test_intro_review(self, intro_cfg):
        assert compute_band(0.55, threshold_override=intro_cfg).band == "review"

    def test_intro_high(self, intro_cfg):
        assert compute_band(0.70, threshold_override=intro_cfg).band == "high"

    # --- mode string dispatch ---

    def test_mode_string_introductory(self):
        assert compute_band(0.72, assignment_mode="introductory").band == "high"

    def test_mode_string_projects(self):
        # projects high_min = 0.55
        assert compute_band(0.55, assignment_mode="projects").band == "high"
        assert compute_band(0.54, assignment_mode="projects").band == "review"

    def test_mode_string_capstone(self):
        # capstone high_min = 0.50
        assert compute_band(0.50, assignment_mode="capstone").band == "high"

    def test_unknown_mode_uses_default(self):
        # default: review=0.35, high=0.65
        assert compute_band(0.65, assignment_mode="unknown_xyz").band == "high"

    # --- score clamping ---

    def test_score_above_1_clamped_to_high(self, algo_cfg):
        assert compute_band(1.5, threshold_override=algo_cfg).band == "high"

    def test_score_below_0_clamped_to_low(self, algo_cfg):
        assert compute_band(-0.1, threshold_override=algo_cfg).band == "low"

    def test_zero_score_is_low(self, algo_cfg):
        assert compute_band(0.0, threshold_override=algo_cfg).band == "low"

    def test_one_score_is_high(self, algo_cfg):
        assert compute_band(1.0, threshold_override=algo_cfg).band == "high"

    # --- allowed_dispositions in result ---

    def test_low_band_dispositions(self, algo_cfg):
        r = compute_band(0.20, threshold_override=algo_cfg)
        assert r.allowed_dispositions == {"no_action", "note_on_file"}

    def test_review_band_includes_conversation(self, algo_cfg):
        r = compute_band(0.50, threshold_override=algo_cfg)
        assert "conversation" in r.allowed_dispositions
        assert "formal_escalation" not in r.allowed_dispositions

    def test_high_band_includes_all(self, algo_cfg):
        r = compute_band(0.80, threshold_override=algo_cfg)
        assert "formal_escalation" in r.allowed_dispositions
        assert "step_up_verification" in r.allowed_dispositions

    # --- thresholds echoed back ---

    def test_thresholds_present_in_result(self, algo_cfg):
        r = compute_band(0.50, threshold_override=algo_cfg)
        assert r.thresholds.review_min == 0.35


# ---------------------------------------------------------------------------
# compute_corroboration — five rules
# ---------------------------------------------------------------------------


class TestComputeCorroboration:
    """compute_corroboration: rule dispatch and output correctness."""

    # --- Rule 4: AI not elevated ---

    def test_rule4_ai_below_threshold(self, algo_cfg):
        r = compute_corroboration(0.60, 0.70, threshold_override=algo_cfg)
        assert r.rule == 4
        assert r.ai_flag is False
        assert r.corroborated is False
        assert r.label == ""
        assert r.blocked_dispositions == frozenset()

    def test_rule4_ai_exactly_below_threshold(self, algo_cfg):
        # ai_elevated_min = 0.65; 0.649 is below
        r = compute_corroboration(0.649, 0.80, threshold_override=algo_cfg)
        assert r.rule == 4
        assert r.ai_flag is False

    def test_rule4_zero_ai_score(self, algo_cfg):
        r = compute_corroboration(0.0, 0.90, threshold_override=algo_cfg)
        assert r.rule == 4

    # --- Rule 3: AI + web match ---

    def test_rule3_web_corroboration(self, algo_cfg):
        r = compute_corroboration(
            0.75, 0.20, threshold_override=algo_cfg, web_match_score=0.80
        )
        assert r.rule == 3
        assert r.ai_flag is True
        assert r.corroborated is True
        assert r.blocked_dispositions == frozenset()
        assert "web" in r.label.lower()

    def test_rule3_exactly_at_web_match_min(self, algo_cfg):
        # web_match_min = 0.70; exactly 0.70 should corroborate
        r = compute_corroboration(
            0.75, 0.20, threshold_override=algo_cfg, web_match_score=0.70
        )
        assert r.rule == 3
        assert r.corroborated is True

    def test_rule3_takes_priority_over_rule2(self, algo_cfg):
        # Both web match AND engine agreement present — Rule 3 fires first
        r = compute_corroboration(
            0.75,
            0.60,
            threshold_override=algo_cfg,
            engine_scores={"ast": 0.80, "token": 0.75},
            web_match_score=0.80,
        )
        assert r.rule == 3

    # --- Rule 2: AI + structural similarity ---

    def test_rule2_engine_agreement_corroborates(self, algo_cfg):
        r = compute_corroboration(
            0.75,
            0.60,  # above review_min=0.35
            threshold_override=algo_cfg,
            engine_scores={"ast": 0.70, "token": 0.65},
        )
        assert r.rule == 2
        assert r.ai_flag is True
        assert r.corroborated is True
        assert r.blocked_dispositions == frozenset()
        assert "similarity" in r.label.lower()

    def test_rule2_requires_enough_engines(self, algo_cfg):
        # Only 1 engine agrees (need 2) — should NOT reach Rule 2
        r = compute_corroboration(
            0.75,
            0.60,
            threshold_override=algo_cfg,
            engine_scores={"ast": 0.70, "token": 0.30},
        )
        assert r.rule != 2
        assert r.corroborated is False

    def test_rule2_requires_similarity_above_review_min(self, algo_cfg):
        # similarity 0.34 < review_min 0.35 — not structural corroboration
        r = compute_corroboration(
            0.75,
            0.34,
            threshold_override=algo_cfg,
            engine_scores={"ast": 0.80, "token": 0.75},
        )
        assert r.rule != 2
        assert r.corroborated is False

    def test_rule2_empty_engine_scores_no_agreement(self, algo_cfg):
        r = compute_corroboration(0.75, 0.60, threshold_override=algo_cfg)
        # No engines provided → agree count = 0 < 2
        assert r.corroborated is False

    # --- Rule 5: High AI, borderline similarity ---

    def test_rule5_high_ai_borderline_similarity(self, algo_cfg):
        # AI >= 0.80, similarity >= 0.10 but < review_min
        r = compute_corroboration(0.85, 0.20, threshold_override=algo_cfg)
        assert r.rule == 5
        assert r.ai_flag is True
        assert r.corroborated is False
        assert HIGH_STAKES_DISPOSITIONS.issubset(r.blocked_dispositions)
        assert "elevated priority" in r.label.lower()

    def test_rule5_requires_ai_ge_080(self, algo_cfg):
        # AI = 0.70 (elevated but < 0.80), similarity = 0.20 → Rule 1 not Rule 5
        r = compute_corroboration(0.70, 0.20, threshold_override=algo_cfg)
        assert r.rule == 1

    def test_rule5_requires_nonzero_similarity(self, algo_cfg):
        # AI = 0.85 but similarity = 0.05 < 0.10 → Rule 1
        r = compute_corroboration(0.85, 0.05, threshold_override=algo_cfg)
        assert r.rule == 1

    # --- Rule 1: AI-only flag ---

    def test_rule1_ai_only_no_corroboration(self, algo_cfg):
        r = compute_corroboration(0.70, 0.20, threshold_override=algo_cfg)
        assert r.rule == 1
        assert r.ai_flag is True
        assert r.corroborated is False
        assert HIGH_STAKES_DISPOSITIONS.issubset(r.blocked_dispositions)
        assert "AI-only flag" in r.label
        assert "not proof" in r.reason

    def test_rule1_blocked_dispositions_are_high_stakes(self, algo_cfg):
        r = compute_corroboration(0.70, 0.20, threshold_override=algo_cfg)
        assert "step_up_verification" in r.blocked_dispositions
        assert "formal_escalation" in r.blocked_dispositions
        # Non-high-stakes dispositions must NOT be blocked
        assert "conversation" not in r.blocked_dispositions
        assert "no_action" not in r.blocked_dispositions

    # --- AI score exactly at threshold boundary ---

    def test_ai_exactly_at_elevated_min_triggers_ai_flag(self, algo_cfg):
        r = compute_corroboration(0.65, 0.20, threshold_override=algo_cfg)
        assert r.ai_flag is True
        assert r.rule in (1, 5)  # elevated but not corroborated

    # --- AI score clamping ---

    def test_ai_score_above_1_clamped(self, algo_cfg):
        r = compute_corroboration(1.5, 0.80, threshold_override=algo_cfg)
        # Still triggers an elevated rule
        assert r.ai_flag is True

    def test_similarity_clamping_does_not_crash(self, algo_cfg):
        r = compute_corroboration(0.70, -0.5, threshold_override=algo_cfg)
        assert r.rule in (1, 5)

    # --- mode string dispatch ---

    def test_mode_string_used_for_thresholds(self):
        # introductory review_min = 0.45; ai_elevated_min = 0.65
        # similarity 0.40 < 0.45 → not structural corroboration even with engines
        r = compute_corroboration(
            0.70,
            0.40,
            assignment_mode="introductory",
            engine_scores={"ast": 0.80, "token": 0.75},
        )
        assert r.rule != 2  # similarity below review_min for introductory


# ---------------------------------------------------------------------------
# allowed_dispositions_for_pair
# ---------------------------------------------------------------------------


class TestAllowedDispositionsForPair:
    """allowed_dispositions_for_pair: intersection of band and corroboration."""

    def test_high_band_no_block_all_available(self, algo_cfg):
        band = compute_band(0.80, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=False, corroborated=False, label="", reason="",
            blocked_dispositions=frozenset(), rule=4
        )
        allowed = allowed_dispositions_for_pair(band, corr)
        assert "formal_escalation" in allowed
        assert "step_up_verification" in allowed

    def test_high_band_ai_only_blocks_high_stakes(self, algo_cfg):
        band = compute_band(0.80, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=True, corroborated=False, label="AI-only flag", reason="x",
            blocked_dispositions=HIGH_STAKES_DISPOSITIONS, rule=1
        )
        allowed = allowed_dispositions_for_pair(band, corr)
        assert "formal_escalation" not in allowed
        assert "step_up_verification" not in allowed
        assert "conversation" in allowed

    def test_review_band_already_excludes_formal_escalation(self, algo_cfg):
        band = compute_band(0.50, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=False, corroborated=False, label="", reason="",
            blocked_dispositions=frozenset(), rule=4
        )
        allowed = allowed_dispositions_for_pair(band, corr)
        assert "formal_escalation" not in allowed

    def test_low_band_only_no_action_and_note(self, algo_cfg):
        band = compute_band(0.10, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=False, corroborated=False, label="", reason="",
            blocked_dispositions=frozenset(), rule=4
        )
        allowed = allowed_dispositions_for_pair(band, corr)
        assert allowed == {"no_action", "note_on_file"}


# ---------------------------------------------------------------------------
# validate_disposition
# ---------------------------------------------------------------------------


class TestValidateDisposition:
    """validate_disposition: acceptance and rejection at each constraint."""

    def test_valid_disposition_accepted(self, algo_cfg):
        band = compute_band(0.80, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=False, corroborated=False, label="", reason="",
            blocked_dispositions=frozenset(), rule=4
        )
        ok, reason = validate_disposition("formal_escalation", band, corr)
        assert ok is True
        assert reason == ""

    def test_invalid_string_rejected(self, algo_cfg):
        band = compute_band(0.80, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=False, corroborated=False, label="", reason="",
            blocked_dispositions=frozenset(), rule=4
        )
        ok, reason = validate_disposition("make_it_go_away", band, corr)
        assert ok is False
        assert "not a valid disposition" in reason

    def test_high_stakes_blocked_by_corroboration(self, algo_cfg):
        band = compute_band(0.80, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=True, corroborated=False, label="AI-only flag",
            reason="needs corroboration",
            blocked_dispositions=HIGH_STAKES_DISPOSITIONS, rule=1
        )
        ok, reason = validate_disposition("step_up_verification", band, corr)
        assert ok is False
        assert "corroborat" in reason.lower()

    def test_disposition_outside_band_rejected(self, algo_cfg):
        # 'formal_escalation' is not in REVIEW_BAND_DISPOSITIONS
        band = compute_band(0.50, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=False, corroborated=False, label="", reason="",
            blocked_dispositions=frozenset(), rule=4
        )
        ok, reason = validate_disposition("formal_escalation", band, corr)
        assert ok is False
        assert "review" in reason.lower()

    def test_no_action_always_valid_in_any_band(self, algo_cfg):
        for score in [0.10, 0.50, 0.80]:
            band = compute_band(score, threshold_override=algo_cfg)
            corr = CorroborationResult(
                ai_flag=True, corroborated=False, label="AI-only flag",
                reason="x", blocked_dispositions=HIGH_STAKES_DISPOSITIONS, rule=1
            )
            ok, _ = validate_disposition("no_action", band, corr)
            assert ok is True, f"no_action should be valid at score={score}"

    def test_conversation_blocked_in_low_band(self, algo_cfg):
        band = compute_band(0.10, threshold_override=algo_cfg)
        corr = CorroborationResult(
            ai_flag=False, corroborated=False, label="", reason="",
            blocked_dispositions=frozenset(), rule=4
        )
        ok, reason = validate_disposition("conversation", band, corr)
        assert ok is False
        assert "low" in reason.lower()


# ---------------------------------------------------------------------------
# Integration: full pair classification
# ---------------------------------------------------------------------------


class TestPairClassificationIntegration:
    """End-to-end: band + corroboration → final allowed dispositions."""

    def test_clean_pair_low_band_no_ai(self, algo_cfg):
        band = compute_band(0.15, threshold_override=algo_cfg)
        corr = compute_corroboration(0.20, 0.15, threshold_override=algo_cfg)
        allowed = allowed_dispositions_for_pair(band, corr)
        assert band.band == "low"
        assert corr.ai_flag is False
        assert allowed == {"no_action", "note_on_file"}

    def test_high_band_corroborated_full_options(self, algo_cfg):
        band = compute_band(0.80, threshold_override=algo_cfg)
        corr = compute_corroboration(
            0.75, 0.80, threshold_override=algo_cfg,
            engine_scores={"ast": 0.80, "token": 0.75}
        )
        allowed = allowed_dispositions_for_pair(band, corr)
        assert band.band == "high"
        assert corr.rule == 2
        assert "formal_escalation" in allowed

    def test_high_band_ai_only_no_high_stakes(self, algo_cfg):
        band = compute_band(0.80, threshold_override=algo_cfg)
        corr = compute_corroboration(0.70, 0.80, threshold_override=algo_cfg)
        # Rule 4 — AI not elevated (0.70 < 0.65 is FALSE; wait — 0.70 >= 0.65)
        # Actually 0.70 >= ai_elevated_min=0.65 but no engine agreement or web match
        # similarity=0.80 >= review_min=0.35 BUT no engine agreement → Rule 1
        allowed = allowed_dispositions_for_pair(band, corr)
        assert "formal_escalation" not in allowed

    def test_review_band_web_match_enables_step_up(self, algo_cfg):
        band = compute_band(0.50, threshold_override=algo_cfg)
        corr = compute_corroboration(
            0.75, 0.50, threshold_override=algo_cfg, web_match_score=0.80
        )
        allowed = allowed_dispositions_for_pair(band, corr)
        assert band.band == "review"
        assert corr.rule == 3
        # step_up_verification is in REVIEW_BAND_DISPOSITIONS and not blocked
        assert "step_up_verification" in allowed
