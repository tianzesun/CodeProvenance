"""Tests for the Binoculars score -> probability mapping.

Regression guard for a real defect: the mapping previously assumed the raw
score was in ``[-1, 1]`` and used ``(1.0 - raw) / 2.0``. The actual
``Binoculars.compute_score`` returns ``perplexity / cross_entropy`` — a
positive ratio around 0.5-1.5 — so confidently-AI text scored 0.75 was mapped
to ``0.125`` (12.5% AI) and the detector could essentially never fire.
"""

from __future__ import annotations

import pytest

from src.backend.engines.ai.binoculars_detector import (
    AI_ANCHOR_PROBABILITY,
    BINOCULARS_ACCURACY_THRESHOLD,
    BINOCULARS_FPR_THRESHOLD,
    HUMAN_ANCHOR_PROBABILITY,
    binoculars_score_to_probability,
)

# The reference implementation classifies a sample as AI when its score is
# below BINOCULARS_FPR_THRESHOLD and human above BINOCULARS_ACCURACY_THRESHOLD.
AI_SCORE = BINOCULARS_FPR_THRESHOLD - 0.10
HUMAN_SCORE = BINOCULARS_ACCURACY_THRESHOLD + 0.10


def test_thresholds_match_the_reference_implementation() -> None:
    """Pinned to the published Binoculars decision thresholds."""
    assert BINOCULARS_FPR_THRESHOLD == pytest.approx(0.8536432310785527)
    assert BINOCULARS_ACCURACY_THRESHOLD == pytest.approx(0.9015310749276843)
    assert BINOCULARS_FPR_THRESHOLD < BINOCULARS_ACCURACY_THRESHOLD


def test_clearly_ai_score_maps_to_high_probability() -> None:
    """A score below the low-FPR threshold is strongly AI."""
    assert binoculars_score_to_probability(AI_SCORE) == pytest.approx(
        AI_ANCHOR_PROBABILITY
    )
    assert binoculars_score_to_probability(0.5) == pytest.approx(AI_ANCHOR_PROBABILITY)


def test_clearly_human_score_maps_to_low_probability() -> None:
    """A score above the accuracy threshold is strongly human."""
    assert binoculars_score_to_probability(HUMAN_SCORE) == pytest.approx(
        HUMAN_ANCHOR_PROBABILITY
    )
    assert binoculars_score_to_probability(1.5) == pytest.approx(
        HUMAN_ANCHOR_PROBABILITY
    )


def test_mapping_decreases_monotonically_with_score() -> None:
    """Lower raw score (more machine-like) must never give a lower probability."""
    scores = [0.60, 0.75, 0.85, 0.88, 0.90, 0.95, 1.10]
    probabilities = [binoculars_score_to_probability(s) for s in scores]
    assert probabilities == sorted(probabilities, reverse=True)


def test_midpoint_lands_between_the_anchors() -> None:
    """A score between the thresholds interpolates rather than saturating."""
    midpoint = (BINOCULARS_FPR_THRESHOLD + BINOCULARS_ACCURACY_THRESHOLD) / 2
    value = binoculars_score_to_probability(midpoint)
    assert HUMAN_ANCHOR_PROBABILITY < value < AI_ANCHOR_PROBABILITY


def test_thresholds_are_inclusive_on_the_ai_side() -> None:
    """Exactly at the low-FPR threshold is still treated as AI."""
    assert binoculars_score_to_probability(BINOCULARS_FPR_THRESHOLD) == pytest.approx(
        AI_ANCHOR_PROBABILITY
    )
    assert binoculars_score_to_probability(
        BINOCULARS_ACCURACY_THRESHOLD
    ) == pytest.approx(HUMAN_ANCHOR_PROBABILITY)


def test_output_is_always_a_probability() -> None:
    """Extreme and degenerate inputs stay inside [0, 1]."""
    for score in (-50.0, 0.0, 1.0, 1e9, float("nan")):
        value = binoculars_score_to_probability(score)
        assert 0.0 <= value <= 1.0
    # NaN is a neutral prior, not a false accusation.
    assert binoculars_score_to_probability(float("nan")) == pytest.approx(0.5)


def test_old_mapping_would_have_missed_confident_ai() -> None:
    """Documents the old defect: the previous formula crushed AI scores.

    ``(1.0 - raw) / 2.0`` for a confidently-AI 0.75 yields 0.125, which is
    below the 0.40 medium-risk band, so the detector could never flag it.
    """
    old_value = (1.0 - 0.75) / 2.0
    assert old_value < 0.40
    assert binoculars_score_to_probability(0.75) > 0.40
