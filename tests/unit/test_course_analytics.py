"""Tests for course & assignment integrity analytics aggregation."""

from src.backend.application.services.course_analytics import (
    assignment_integrity_stats,
    course_integrity_summary,
    risk_band,
)


def test_risk_band_boundaries() -> None:
    """Risk bands follow the CRITICAL/HIGH/MEDIUM/LOW thresholds."""
    assert risk_band(0.9) == "CRITICAL"
    assert risk_band(0.85) == "CRITICAL"
    assert risk_band(0.7) == "HIGH"
    assert risk_band(0.65) == "HIGH"
    assert risk_band(0.4) == "MEDIUM"
    assert risk_band(0.35) == "MEDIUM"
    assert risk_band(0.1) == "LOW"


def test_assignment_stats_empty() -> None:
    """An assignment with no pairs returns zeroed stats and a full distribution."""
    stats = assignment_integrity_stats([])
    assert stats["pair_count"] == 0
    assert stats["avg_similarity"] == 0.0
    assert stats["flagged_pairs"] == 0
    assert stats["high_pairs"] == 0
    assert "distribution" in stats


def test_assignment_stats_averages_and_bands() -> None:
    """Mean/median/max and band counts are computed from similarity scores."""
    pairs = [
        {"similarity_score": 0.9},  # critical
        {"similarity_score": 0.7},  # high
        {"similarity_score": 0.4},  # medium
        {"similarity_score": 0.1},  # low
        {"similarity_score": 0.2},  # low
    ]
    stats = assignment_integrity_stats(pairs, flag_threshold=0.35)
    assert stats["pair_count"] == 5
    assert stats["avg_similarity"] == round(2.3 / 5, 4)
    assert stats["median_similarity"] == 0.4
    assert stats["max_similarity"] == 0.9
    assert stats["flagged_pairs"] == 3
    assert round(stats["flagged_fraction"], 4) == round(3 / 5, 4)
    # 0.9 critical + 0.7 high -> high_pairs groups critical+high
    assert stats["high_pairs"] == 2
    assert stats["medium_pairs"] == 1
    assert stats["low_pairs"] == 2


def test_assignment_stats_respects_stored_risk_level() -> None:
    """A row with a stored risk_level wins over score-derived band."""
    pairs = [{"similarity_score": 0.95, "risk_level": "LOW"}]
    stats = assignment_integrity_stats(pairs)
    assert stats["low_pairs"] == 1
    assert stats["high_pairs"] == 0


def test_course_summary_ranks_assignments_by_risk() -> None:
    """Course summary aggregates assignments and ranks the riskiest first."""
    assignments = [
        {
            "assignment": {"id": "1", "name": "A1", "assignment_type": "programming"},
            "stats": assignment_integrity_stats(
                [{"similarity_score": 0.9}, {"similarity_score": 0.8}]
            ),
            "pairs": [{"similarity_score": 0.9}, {"similarity_score": 0.8}],
        },
        {
            "assignment": {"id": "2", "name": "A2", "assignment_type": "written"},
            "stats": assignment_integrity_stats([{"similarity_score": 0.2}]),
            "pairs": [{"similarity_score": 0.2}],
        },
    ]
    summary = course_integrity_summary(assignments)
    assert summary["assignment_count"] == 2
    assert summary["flagged_assignments"] == 1
    assert summary["top_risk_assignments"][0]["id"] == "1"
    # rolled-up avg across all three pairs
    assert summary["pair_count"] == 3
    assert summary["max_similarity"] == 0.9
