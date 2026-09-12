"""Course and assignment integrity analytics.

Aggregation is computed from detached row dicts so the functions are pure and
unit-testable without a database. The FastAPI layer feeds these functions rows
loaded from ``SimilarityResult``/``Job``. Derived analytics are kept separate
from raw detection data (see docs/ARCHITECTURE.md); a cache/materialized-view
layer can be added later without changing these contracts.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any

# Review priority / risk bands — aligned with
# ``src.backend.application.services.dashboard_service.RISK_LEVELS``.
RISK_LEVELS: list[tuple[float, str]] = [
    (0.85, "CRITICAL"),
    (0.65, "HIGH"),
    (0.35, "MEDIUM"),
    (0.0, "LOW"),
]

# Histogram bucket edges for the similarity distribution (0..1).
DISTRIBUTION_BUCKETS: list[tuple[float, float]] = [
    (0.0, 0.2),
    (0.2, 0.35),
    (0.35, 0.5),
    (0.5, 0.65),
    (0.65, 0.85),
    (0.85, 1.0001),
]


def risk_band(score: float) -> str:
    """Map a similarity score (0..1) to its risk band."""
    for threshold, level in RISK_LEVELS:
        if score >= threshold:
            return level
    return "LOW"


def _band_of(row: dict[str, Any]) -> str:
    """Resolve the risk band for a row, preferring stored risk_level."""
    stored = (row.get("risk_level") or "").upper()
    if stored in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        return stored
    return risk_band(float(row.get("similarity_score") or 0.0))


def assignment_integrity_stats(
    pairs: list[dict[str, Any]],
    flag_threshold: float = 0.35,
) -> dict[str, Any]:
    """Compute an assignment-level integrity profile from similarity pairs.

    Args:
        pairs: Detached rows; each should carry ``similarity_score`` (and an
            optional ``risk_level``).
        flag_threshold: Minimum similarity to count a pair as flagged.

    Returns:
        Aggregated stats: mean/median/max similarity, flagged/high/medium/low
        pair counts, flagged fraction, and a score distribution.
    """
    scores = [float(p.get("similarity_score") or 0.0) for p in pairs]
    n = len(scores)
    if n == 0:
        return {
            "pair_count": 0,
            "avg_similarity": 0.0,
            "median_similarity": 0.0,
            "max_similarity": 0.0,
            "flagged_pairs": 0,
            "flagged_fraction": 0.0,
            "high_pairs": 0,
            "medium_pairs": 0,
            "low_pairs": 0,
            "distribution": {
                f"{lo:.0%}-{hi:.0%}".replace(".0%", "%"): 0
                for lo, hi in DISTRIBUTION_BUCKETS
            },
        }

    flagged = [s for s in scores if s >= flag_threshold]
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for row in pairs:
        counts[_band_of(row)] = counts.get(_band_of(row), 0) + 1

    distribution: dict[str, int] = {}
    for lo, hi in DISTRIBUTION_BUCKETS:
        key = f"{_pct(lo)}-{_pct(min(hi, 1.0))}"
        distribution[key] = sum(1 for s in scores if lo <= s < hi)

    return {
        "pair_count": n,
        "avg_similarity": round(mean(scores), 4),
        "median_similarity": round(median(scores), 4),
        "max_similarity": round(max(scores), 4),
        "flagged_pairs": len(flagged),
        "flagged_fraction": round(len(flagged) / n, 4),
        "high_pairs": counts["HIGH"] + counts["CRITICAL"],
        "medium_pairs": counts["MEDIUM"],
        "low_pairs": counts["LOW"],
        "distribution": distribution,
    }


def _pct(value: float) -> str:
    """Format a 0..1 value as an integer percentage, saturating at 100."""
    return f"{int(round(value * 100))}%"


def course_integrity_summary(
    assignments: list[dict[str, Any]],
    all_pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate per-assignment integrity profiles into a course summary.

    Args:
        assignments: List of ``{"assignment": {...}, "stats": {...}}`` entries.
        all_pairs: Optional global list of all pairs across the course (used to
            compute course-level stats); when omitted the per-assignment pair
            lists are concatenated.

    Returns:
        Rolled-up course stats plus a risk-priority assignment ranking.
    """
    if all_pairs is None:
        all_pairs = [pair for entry in assignments for pair in entry.get("pairs", [])]

    summary = assignment_integrity_stats(all_pairs)
    summary["assignment_count"] = len(assignments)
    summary["flagged_assignments"] = sum(
        1 for a in assignments if a["stats"].get("flagged_pairs", 0) > 0
    )
    summary["top_risk_assignments"] = sorted(
        [
            {
                "id": a["assignment"].get("id"),
                "name": a["assignment"].get("name"),
                "assignment_type": a["assignment"].get("assignment_type"),
                "avg_similarity": a["stats"].get("avg_similarity", 0.0),
                "max_similarity": a["stats"].get("max_similarity", 0.0),
                "flagged_pairs": a["stats"].get("flagged_pairs", 0),
                "high_pairs": a["stats"].get("high_pairs", 0),
            }
            for a in assignments
        ],
        key=lambda a: (a["flagged_pairs"], a["avg_similarity"]),
        reverse=True,
    )
    return summary
