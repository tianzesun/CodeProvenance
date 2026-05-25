"""Same wrong-answer / same-bug detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class RuntimeOutcome:
    """Observed output for one generated runtime test."""

    test_id: str
    output: str = ""
    expected_output: Optional[str] = None
    exception_type: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class SameBugFinding:
    """Same-bug detection result."""

    score: float
    same_wrong_outputs: List[str]
    same_exceptions: List[str]
    same_timeouts: List[str]
    evidence: List[str]


class SameBugDetector:
    """Detect shared wrong outputs, exceptions, and timeout behavior."""

    def compare(
        self,
        outcomes_a: Iterable[RuntimeOutcome],
        outcomes_b: Iterable[RuntimeOutcome],
    ) -> SameBugFinding:
        """Compare runtime outcomes from two submissions."""
        by_id_a = {outcome.test_id: outcome for outcome in outcomes_a}
        by_id_b = {outcome.test_id: outcome for outcome in outcomes_b}
        shared_ids = sorted(set(by_id_a) & set(by_id_b))

        same_wrong_outputs: List[str] = []
        same_exceptions: List[str] = []
        same_timeouts: List[str] = []

        for test_id in shared_ids:
            left = by_id_a[test_id]
            right = by_id_b[test_id]
            if left.timed_out and right.timed_out:
                same_timeouts.append(test_id)
                continue
            if left.exception_type and left.exception_type == right.exception_type:
                same_exceptions.append(test_id)
                continue
            if self._same_wrong_output(left, right):
                same_wrong_outputs.append(test_id)

        evidence = []
        if same_wrong_outputs:
            evidence.append("same wrong outputs")
        if same_exceptions:
            evidence.append("same exception behavior")
        if same_timeouts:
            evidence.append("same timeout pattern")

        total = max(len(shared_ids), 1)
        weighted_matches = (
            len(same_wrong_outputs) * 1.0
            + len(same_exceptions) * 0.9
            + len(same_timeouts) * 0.8
        )
        score = min(1.0, weighted_matches / total)

        return SameBugFinding(
            score=round(score, 4),
            same_wrong_outputs=same_wrong_outputs,
            same_exceptions=same_exceptions,
            same_timeouts=same_timeouts,
            evidence=evidence,
        )

    def _same_wrong_output(self, left: RuntimeOutcome, right: RuntimeOutcome) -> bool:
        """Return true if both submissions produced the same incorrect output."""
        if left.expected_output is None or right.expected_output is None:
            return False
        normalized_left = self._normalize_output(left.output)
        normalized_right = self._normalize_output(right.output)
        normalized_expected = self._normalize_output(left.expected_output)
        return (
            normalized_left == normalized_right
            and normalized_left != normalized_expected
        )

    def _normalize_output(self, value: str) -> str:
        """Normalize output text before comparing runtime behavior."""
        return " ".join((value or "").strip().lower().split())
