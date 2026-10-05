"""Precision@K ranking utilities for professor review queues.

What changed: a case without a ``label`` used to count as a NEGATIVE (``label`` defaulted to 0), so
an unlabeled queue produced a confident-looking, wrong Precision@20. Unlabeled cases are now left
out of the evaluation, an evaluation with no labels raises, and labels must be 0/1. A ``case_id`` of
``0`` no longer falls through to ``case_<index>`` (``or`` treated it as missing), ``features: None``
is accepted, and duplicate ids are rejected (they made the ranking ambiguous).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.backend.engines.scoring.evidence_ranker import EvidenceFusionRanker
from src.backend.evaluation.proof_system import ProofCase
from src.backend.evaluation.proof_system import precision_at_k as _precision_at_k


@dataclass(frozen=True)
class RankedCase:
    """One case after evidence fusion ranking."""

    case_id: str
    review_priority: float
    confidence: str
    professor_summary: str
    reasons: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


def _case_id(case: Mapping[str, Any], index: int) -> str:
    for key in ("case_id", "id"):
        value = case.get(key)
        if value is not None and str(value) != "":
            return str(value)
    return f"case_{index}"


class PrecisionAt20Ranker:
    """Rank cases by review priority and evaluate Precision@K when labels exist."""

    def __init__(self, ranker: EvidenceFusionRanker | None = None) -> None:
        self.ranker = ranker or EvidenceFusionRanker()

    def rank(self, cases: Iterable[Mapping[str, Any]]) -> list[RankedCase]:
        """Rank case dictionaries containing ``case_id`` (or ``id``) and ``features``."""
        ranked: list[RankedCase] = []
        seen: set[str] = set()
        for index, case in enumerate(cases):
            case_id = _case_id(case, index)
            if case_id in seen:
                raise ValueError(f"duplicate case id {case_id!r}")
            seen.add(case_id)
            result = self.ranker.rank_pair(case.get("features") or {}, base_score=case.get("base_score"))
            ranked.append(
                RankedCase(
                    case_id=case_id,
                    review_priority=result.review_priority,
                    confidence=result.confidence,
                    professor_summary=result.professor_summary,
                    reasons=result.reasons,
                    guardrails=result.guardrails,
                    payload=dict(case),
                )
            )
        return sorted(ranked, key=lambda item: (-item.review_priority, item.case_id))

    def precision_at_k(self, cases: Iterable[Mapping[str, Any]], k: int = 20) -> float:
        """Rank the LABELED cases and compute Precision@K.

        Raises:
            ValueError: no case has a label, or a label is not 0/1.
        """
        labeled = []
        for item in self.rank(cases):
            label = item.payload.get("label")
            if label is None:
                continue
            if isinstance(label, bool):
                label = int(label)
            if label not in (0, 1):
                raise ValueError(f"case {item.case_id!r}: label must be 0 or 1, got {label!r}")
            labeled.append(
                ProofCase(
                    case_id=item.case_id,
                    score=item.review_priority,
                    label=int(label),
                    category=str(item.payload.get("category", "unknown")),
                )
            )
        if not labeled:
            raise ValueError("Precision@K needs at least one case with a 'label'")
        return round(_precision_at_k(labeled, k), 4)

    def precision_at_20(self, cases: Iterable[Mapping[str, Any]]) -> float:
        """Rank labeled cases and compute Precision@20."""
        return self.precision_at_k(cases, 20)
