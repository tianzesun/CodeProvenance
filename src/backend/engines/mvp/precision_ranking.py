"""Precision@20 ranking utilities for professor review queues."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping

from src.backend.engines.scoring.evidence_ranker import EvidenceFusionRanker
from src.backend.evaluation.proof_system import ProofCase, precision_at_k


@dataclass(frozen=True)
class RankedCase:
    """One case after evidence fusion ranking."""

    case_id: str
    review_priority: float
    confidence: str
    professor_summary: str
    reasons: List[str] = field(default_factory=list)
    guardrails: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)


class PrecisionAt20Ranker:
    """Rank cases by review priority and evaluate Precision@20 when labels exist."""

    def __init__(self, ranker: EvidenceFusionRanker | None = None) -> None:
        self.ranker = ranker or EvidenceFusionRanker()

    def rank(self, cases: Iterable[Mapping[str, Any]]) -> List[RankedCase]:
        """Rank case dictionaries containing `case_id` and `features`."""
        ranked: List[RankedCase] = []
        for index, case in enumerate(cases):
            case_id = str(case.get("case_id") or case.get("id") or f"case_{index}")
            result = self.ranker.rank_pair(
                case.get("features", {}),
                base_score=case.get("base_score"),
            )
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

    def precision_at_20(self, cases: Iterable[Mapping[str, Any]]) -> float:
        """Rank labeled cases and compute Precision@20."""
        ranked = self.rank(cases)
        proof_cases = [
            ProofCase(
                case_id=item.case_id,
                score=item.review_priority,
                label=int(item.payload.get("label", 0)),
                category=str(item.payload.get("category", "unknown")),
            )
            for item in ranked
        ]
        return round(precision_at_k(proof_cases, 20), 4)
