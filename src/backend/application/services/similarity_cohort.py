"""Cohort context for similarity scores.

A pairwise similarity score answers "how much do these two submissions look
alike", not "how likely is it that this pair cheated". On the labeled corpora
the two questions diverge sharply: independent solutions of the same assignment
already score a median of 0.878 (IR-Plag) and 0.775 (kaggle_student_code), so a
job that presents the score alone invites reading it as a probability. Each job
therefore also carries the distribution its pairs were ranked in.

This module is deliberately descriptive: it never rescales a score. Dividing a
score by the cohort median removes a false-positive wall in an ordinary class
and hides real plagiarism where the clean pairs are themselves near-duplicates
(positively-flagged pairs on IR-Plag drop from 99% to 41%), so that decision is
left to a human with the context in front of them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

COHORT_DISCLOSURE = (
    "Similarity scores rank pairs; they are not a probability of plagiarism. "
    "Independent solutions to the same assignment can score high, so review the "
    "highest-ranked pairs rather than everything above a fixed cut-off."
)


def _quantile(ordered: Sequence[float], fraction: float) -> float:
    """Return a linearly interpolated quantile of an ordered sequence."""
    if not ordered:
        return 0.0
    position = fraction * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def percentile_rank(score: float, scores: Sequence[float]) -> float:
    """Return the share of the cohort at or below ``score``, ties halved.

    Midrank ties matter here: on several corpora a large block of pairs sits at
    exactly 1.0, and counting every one of them as top-of-class would make the
    number meaningless.
    """
    if not scores:
        return 0.0
    below = sum(1 for value in scores if value < score)
    equal = sum(1 for value in scores if value == score)
    return (below + 0.5 * equal) / len(scores)


@dataclass(frozen=True)
class CohortContext:
    """The score distribution a job's pairs were ranked in."""

    size: int
    median: float
    p25: float
    p75: float

    @classmethod
    def from_scores(cls, scores: Iterable[float]) -> CohortContext:
        """Summarise a cohort from its pairwise scores."""
        ordered = sorted(float(score) for score in scores)
        return cls(
            size=len(ordered),
            median=round(_quantile(ordered, 0.5), 4),
            p25=round(_quantile(ordered, 0.25), 4),
            p75=round(_quantile(ordered, 0.75), 4),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe form carried by a job payload."""
        return {
            "size": self.size,
            "median": self.median,
            "p25": self.p25,
            "p75": self.p75,
            "disclosure": COHORT_DISCLOSURE,
        }


def annotate_results(
    results: list[dict[str, Any]],
    key: str = "score",
    scores: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Stamp each result with its cohort percentile and return the context.

    Mutates ``results`` in place: the percentile is per pair, the context is per
    job. Rows without a numeric score keep no percentile.

    Args:
        results: Job result rows, each holding a numeric similarity under
            ``key``.
        key: Field that holds the similarity score.
        scores: Full cohort when ``results`` is a truncated slice (the database
            reader caps its page). Percentiles must be computed against the
            cohort, not against whatever page happened to be returned.

    Returns:
        The cohort context as a JSON-safe dict.
    """
    scored = [row for row in results if isinstance(row.get(key), (int, float))]
    cohort = (
        [float(score) for score in scores]
        if scores is not None
        else [float(row[key]) for row in scored]
    )
    for row in scored:
        row["cohort_percentile"] = round(percentile_rank(float(row[key]), cohort), 4)
    return CohortContext.from_scores(cohort).to_dict()
