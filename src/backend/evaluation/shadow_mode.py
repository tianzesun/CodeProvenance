"""Shadow-mode feedback collection for professor review validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class ShadowFeedback:
    """A professor/TA judgment captured without affecting students."""

    case_id: str
    reviewer_id: str
    worth_reviewing: bool
    decision: str
    review_time_seconds: int
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass(frozen=True)
class ShadowModeSummary:
    """Aggregate shadow-mode evidence for launch readiness."""

    feedback_count: int
    worth_reviewing_rate: float
    median_review_time_seconds: float
    decision_counts: Dict[str, int]


class ShadowModeFeedbackStore:
    """In-memory store for shadow-mode feedback.

    Production can back this interface with a database table. The aggregate
    metrics are intentionally simple: they answer whether Top-N cases were worth
    professor time before cases are allowed to affect students.
    """

    def __init__(self) -> None:
        self._feedback: List[ShadowFeedback] = []

    def add(self, feedback: ShadowFeedback) -> None:
        """Record one shadow-mode reviewer judgment."""
        self._feedback.append(feedback)

    def extend(self, feedback_items: Iterable[ShadowFeedback]) -> None:
        """Record multiple shadow-mode reviewer judgments."""
        self._feedback.extend(feedback_items)

    def list_feedback(self) -> List[ShadowFeedback]:
        """Return all feedback records."""
        return list(self._feedback)

    def summary(self) -> ShadowModeSummary:
        """Aggregate feedback into launch-readiness metrics."""
        if not self._feedback:
            return ShadowModeSummary(
                feedback_count=0,
                worth_reviewing_rate=0.0,
                median_review_time_seconds=0.0,
                decision_counts={},
            )

        worth_reviewing = sum(1 for item in self._feedback if item.worth_reviewing)
        times = sorted(item.review_time_seconds for item in self._feedback)
        midpoint = len(times) // 2
        if len(times) % 2:
            median = float(times[midpoint])
        else:
            median = (times[midpoint - 1] + times[midpoint]) / 2

        decision_counts: Dict[str, int] = {}
        for item in self._feedback:
            decision_counts[item.decision] = decision_counts.get(item.decision, 0) + 1

        return ShadowModeSummary(
            feedback_count=len(self._feedback),
            worth_reviewing_rate=round(worth_reviewing / len(self._feedback), 4),
            median_review_time_seconds=round(median, 2),
            decision_counts=decision_counts,
        )
