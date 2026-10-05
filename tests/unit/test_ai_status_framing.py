"""The AI status label must describe a review priority, not a verdict.

Measured grouped-holdout AUC for the detector is ~0.53 (see
``docs/AI_DETECTION_ACCURACY_FINDINGS.md``): it misses assisted code and flags
some honest submissions. "High Risk" / "Low Risk" language reads as a finding
about the student, and "Low Risk" in particular clears a file the detector
simply failed to flag. These tests pin the reframed vocabulary so it cannot
quietly drift back into verdict language.
"""

from __future__ import annotations

import pytest

from src.backend.api.server import (
    AI_HIGH_RISK_THRESHOLD,
    AI_MEDIUM_RISK_THRESHOLD,
    _ai_status_label,
)

TRIAGE_LABELS = {
    "Review first",
    "Worth a look",
    "Possible AI assistance",
    "No clear signal",
}

#: Ascending priority. A higher score must never read as a lower priority, so the
#: order is declared here rather than inferred from set iteration.
PRIORITY_ORDER = [
    "No clear signal",
    "Possible AI assistance",
    "Worth a look",
    "Review first",
]

VERDICT_LABELS = {
    "High Risk",
    "Low Risk",
    "Needs Review",
    "Possibly Refactored AI Code",
}


class TestStatusLabelsAreTriageNotVerdict:
    """Every band reports what to do next, not what was concluded."""

    @pytest.mark.parametrize(
        "score", [0.0, 0.05, 0.2, 0.34, 0.36, 0.39, 0.41, 0.6, 0.69, 0.71, 0.9, 1.0]
    )
    def test_labels_never_use_risk_language(self, score: float) -> None:
        label = _ai_status_label(score)

        assert label in TRIAGE_LABELS
        assert label not in VERDICT_LABELS

    def test_bands_are_monotonic_in_priority(self) -> None:
        """A higher score never reads as a lower priority."""
        scores = [0.0, 0.36, 0.45, 0.75]
        order = [PRIORITY_ORDER.index(_ai_status_label(s)) for s in scores]

        assert order == sorted(order)

    def test_low_score_says_no_signal_not_cleared(self) -> None:
        """ "No clear signal" reports absence of evidence, not evidence of absence."""
        assert _ai_status_label(0.0) == "No clear signal"
        assert "risk" not in _ai_status_label(0.0).lower()

    def test_high_band_asks_for_a_review_rather_than_asserting_fault(self) -> None:
        label = _ai_status_label(AI_HIGH_RISK_THRESHOLD)

        assert label == "Review first"
        assert "risk" not in label.lower()

    def test_medium_band_is_inclusive_of_its_threshold(self) -> None:
        assert _ai_status_label(AI_MEDIUM_RISK_THRESHOLD) == "Worth a look"

    def test_refactor_floor_still_surfaces_edited_assistance(self) -> None:
        """Heavily paraphrased AI code must not fall through to the bottom band."""
        between = (AI_MEDIUM_RISK_THRESHOLD + 0.36) / 2
        if 0.36 < between < AI_MEDIUM_RISK_THRESHOLD:
            assert _ai_status_label(between) == "Possible AI assistance"
