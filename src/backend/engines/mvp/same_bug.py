"""Same wrong-answer / same-bug detection.

Two submissions that fail the SAME tests in the SAME way are far stronger evidence of a common
source than two that merely pass the same tests. What changed:

- The score was matches divided by ALL shared tests. Two submissions that share every one of their
  3 failures out of 100 tests scored 0.03, so the ranker's ``>= 0.70`` shared-bug rule could
  essentially never fire. The denominator is now the tests where at least one of them FAILS.
- One coincidence is not evidence: the score is scaled by ``min(1, shared / 3)``.
- An exception counted as a bug even when the test EXPECTS that exception
  (``expected_exception``), and the same wrong output was only checked against ``left``'s expected
  output.
- A timeout is the weakest signal (a naive but correct solution times out on a big input), so it
  weighs 0.5, not 0.8.
- Optional ``common_failure_rates`` (fraction of the class failing each test) discounts failures
  everyone has, which are not evidence of copying.
- Output comparison is case-sensitive by default (lower-casing made ``yes`` equal to ``Yes`` and so
  hid shared wrong-case outputs).
- Two blank/never-run submissions fail identically; the pipeline gates on that, this module cannot
  know.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeOutcome:
    """Observed output for one generated runtime test."""

    test_id: str
    output: str = ""
    expected_output: str | None = None
    exception_type: str = ""
    timed_out: bool = False
    #: exception type the test EXPECTS (invalid-input tests); observing it is correct behaviour
    expected_exception: str = ""


@dataclass(frozen=True)
class SameBugFinding:
    """Same-bug detection result."""

    score: float
    same_wrong_outputs: list[str]
    same_exceptions: list[str]
    same_timeouts: list[str]
    evidence: list[str]
    shared_failures: int = 0
    failing_union: int = 0  # tests where at least one submission fails
    compared_tests: int = 0
    reliability: float = 0.0  # min(1, shared_failures / min_shared_for_full)


class SameBugDetector:
    """Detect shared wrong outputs, exceptions, and timeout behavior."""

    def __init__(
        self,
        *,
        case_sensitive: bool = True,
        wrong_output_weight: float = 1.0,
        exception_weight: float = 0.9,
        timeout_weight: float = 0.5,
        min_shared_for_full: int = 3,
    ) -> None:
        if min_shared_for_full < 1:
            raise ValueError("min_shared_for_full must be at least 1")
        self.case_sensitive = case_sensitive
        self.wrong_output_weight = wrong_output_weight
        self.exception_weight = exception_weight
        self.timeout_weight = timeout_weight
        self.min_shared_for_full = min_shared_for_full

    def compare(
        self,
        outcomes_a: Iterable[RuntimeOutcome],
        outcomes_b: Iterable[RuntimeOutcome],
        common_failure_rates: Mapping[str, float] | None = None,
    ) -> SameBugFinding:
        """Compare runtime outcomes from two submissions.

        Args:
            common_failure_rates: optional ``{test_id: fraction of the class that fails it}``;
                a shared failure on a test that most of the class fails counts for less.
        """
        by_id_a = {o.test_id: o for o in outcomes_a}
        by_id_b = {o.test_id: o for o in outcomes_b}
        shared_ids = sorted(set(by_id_a) & set(by_id_b))
        rates = common_failure_rates or {}

        same_wrong: list[str] = []
        same_exc: list[str] = []
        same_timeout: list[str] = []
        failing_union = 0
        weighted = 0.0

        for test_id in shared_ids:
            left, right = by_id_a[test_id], by_id_b[test_id]
            kind_a, kind_b = self._failure(left), self._failure(right)
            if kind_a is None and kind_b is None:
                continue
            failing_union += 1
            if kind_a is None or kind_b is None or kind_a[0] != kind_b[0] or kind_a[1] != kind_b[1]:
                continue  # one passes, or they fail differently
            kind = kind_a[0]
            if kind == "wrong" and self._normalize_output(left.expected_output or "") != self._normalize_output(
                right.expected_output or ""
            ):
                continue  # different expectations: not the same test after all
            rate = self._rate(rates.get(test_id))
            if kind == "timeout":
                same_timeout.append(test_id)
                weight = self.timeout_weight
            elif kind == "exception":
                same_exc.append(test_id)
                weight = self.exception_weight
            else:
                same_wrong.append(test_id)
                weight = self.wrong_output_weight
            weighted += weight * (1.0 - rate)

        shared = len(same_wrong) + len(same_exc) + len(same_timeout)
        reliability = min(1.0, shared / self.min_shared_for_full)
        score = min(1.0, weighted / failing_union) * reliability if failing_union else 0.0

        evidence = []
        if same_wrong:
            evidence.append(f"same wrong outputs on {len(same_wrong)} test(s)")
        if same_exc:
            evidence.append(f"same exception behavior on {len(same_exc)} test(s)")
        if same_timeout:
            evidence.append(f"same timeout pattern on {len(same_timeout)} test(s)")
        if failing_union:
            evidence.append(f"{shared} of {failing_union} failing test(s) fail identically")

        return SameBugFinding(
            score=round(score, 4),
            same_wrong_outputs=same_wrong,
            same_exceptions=same_exc,
            same_timeouts=same_timeout,
            evidence=evidence,
            shared_failures=shared,
            failing_union=failing_union,
            compared_tests=len(shared_ids),
            reliability=round(reliability, 4),
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _rate(value: float | None) -> float:
        try:
            number = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
        return min(1.0, max(0.0, number)) if math.isfinite(number) else 0.0

    def _failure(self, outcome: RuntimeOutcome) -> tuple[str, str] | None:
        """``(kind, detail)`` when the outcome is a failure, else None.

        kind is timeout / exception (detail = type) / wrong (detail = normalised output).
        """
        if outcome.timed_out:
            return "timeout", ""
        if outcome.exception_type:
            if outcome.exception_type == outcome.expected_exception:
                return None  # the test asks for this exception
            return "exception", outcome.exception_type
        if outcome.expected_output is None:
            return None  # nothing to compare against: not a known failure
        got, want = self._normalize_output(outcome.output), self._normalize_output(outcome.expected_output)
        return None if got == want else ("wrong", got)

    def _same_wrong_output(self, left: RuntimeOutcome, right: RuntimeOutcome) -> bool:
        """True if both produced the same incorrect output for the same expectation."""
        if left.expected_output is None or right.expected_output is None:
            return False
        if self._normalize_output(left.expected_output) != self._normalize_output(right.expected_output):
            return False  # different expectations: not the same test
        a, b = self._failure(left), self._failure(right)
        return a is not None and b is not None and a[0] == "wrong" and a == b

    def _normalize_output(self, value: str) -> str:
        """Collapse whitespace (and case, when ``case_sensitive`` is False)."""
        text = " ".join((value or "").strip().split())
        return text if self.case_sensitive else text.lower()
