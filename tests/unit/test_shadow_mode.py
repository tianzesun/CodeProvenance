"""Tests for shadow-mode professor feedback aggregation."""

from src.backend.evaluation.shadow_mode import ShadowFeedback, ShadowModeFeedbackStore


def test_shadow_mode_summary_aggregates_professor_feedback() -> None:
    """Shadow mode should measure whether ranked cases were worth reviewing."""
    store = ShadowModeFeedbackStore()
    store.extend(
        [
            ShadowFeedback("c1", "prof_a", True, "confirmed", 110),
            ShadowFeedback("c2", "prof_a", True, "marked", 130),
            ShadowFeedback("c3", "ta_b", False, "dismissed", 45),
        ]
    )

    summary = store.summary()

    assert summary.feedback_count == 3
    assert summary.worth_reviewing_rate == 0.6667
    assert summary.median_review_time_seconds == 110
    assert summary.decision_counts == {"confirmed": 1, "marked": 1, "dismissed": 1}


def test_shadow_mode_empty_summary_is_stable() -> None:
    """Empty shadow-mode summaries should be safe for dashboards."""
    summary = ShadowModeFeedbackStore().summary()

    assert summary.feedback_count == 0
    assert summary.worth_reviewing_rate == 0.0
    assert summary.decision_counts == {}
