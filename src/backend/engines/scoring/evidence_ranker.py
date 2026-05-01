"""Evidence-first ranking for professor review queues.

This module intentionally does not compute a plain weighted average. It applies
precision guardrails around the strongest classroom evidence: starter-code
discounting, common-solution discounting, same-bug boosts, previous-term
matching, and multi-engine agreement. The output is a review-priority rank, not
an allegation or final misconduct probability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional


def _clamp(value: float) -> float:
    """Clamp numeric scores to the unit interval."""
    return max(0.0, min(1.0, float(value)))


def _get(features: Mapping[str, float], key: str) -> float:
    """Read and clamp a feature value from a sparse feature mapping."""
    return _clamp(float(features.get(key, 0.0) or 0.0))


@dataclass(frozen=True)
class EvidenceRank:
    """Ranker result suitable for professor-facing queues."""

    review_priority: float
    risk_score: float
    confidence: str
    reasons: List[str] = field(default_factory=list)
    guardrails: List[str] = field(default_factory=list)
    professor_summary: str = ""
    features: Dict[str, float] = field(default_factory=dict)


class EvidenceFusionRanker:
    """Rule-guarded evidence ranker optimized for top-k professor review.

    Production training can replace the base scorer with Logistic Regression,
    XGBoost/LightGBM, or learning-to-rank. The objective should be Precision@10,
    Precision@20, NDCG@20, and recall at a fixed false-positive rate. The
    guardrails in this class should remain in front of any learned score.
    """

    concrete_keys = (
        "fingerprint",
        "winnowing",
        "ast",
        "cfg_similarity",
        "dfg_similarity",
        "call_graph_similarity",
        "edge_case_behavior_similarity",
        "runtime_bug_similarity",
    )

    def rank_pair(
        self,
        features: Mapping[str, float],
        *,
        base_score: Optional[float] = None,
    ) -> EvidenceRank:
        """Rank a pair for review using multi-layer evidence and guardrails."""
        normalized = {key: _clamp(value) for key, value in features.items()}

        token = max(_get(normalized, "fingerprint"), _get(normalized, "winnowing"))
        ast = _get(normalized, "ast")
        cfg = _get(normalized, "cfg_similarity")
        dfg = _get(normalized, "dfg_similarity")
        call_graph = _get(normalized, "call_graph_similarity")
        runtime_bug = _get(normalized, "runtime_bug_similarity")
        edge_case = _get(normalized, "edge_case_behavior_similarity")
        previous_term = _get(normalized, "previous_term_match")
        rare_pattern = _get(normalized, "rare_pattern_score")
        identifier_rename = _get(normalized, "identifier_rename_score")
        starter_overlap = _get(normalized, "starter_code_overlap")
        boilerplate_overlap = _get(normalized, "boilerplate_overlap")
        common_solution = _get(normalized, "common_solution_score")
        style_shift = _get(normalized, "student_style_shift")
        embedding = _get(normalized, "embedding")

        if base_score is None:
            base_score = (
                token * 0.18
                + ast * 0.20
                + cfg * 0.12
                + dfg * 0.10
                + call_graph * 0.08
                + runtime_bug * 0.16
                + edge_case * 0.08
                + previous_term * 0.08
            )

        score = _clamp(base_score)
        reasons: List[str] = []
        guardrails: List[str] = []

        if starter_overlap >= 0.70:
            score *= 0.55
            guardrails.append("Discounted shared starter-code regions.")
        if boilerplate_overlap >= 0.70:
            score *= 0.75
            guardrails.append("Discounted boilerplate overlap.")
        if common_solution >= 0.65:
            score *= 0.70
            guardrails.append(
                "Lowered risk because the pattern matches a common solution cluster."
            )

        if runtime_bug >= 0.70 or edge_case >= 0.75:
            score = max(score, 0.86)
            reasons.append(
                "Both submissions share the same wrong or edge-case behavior."
            )
        if previous_term >= 0.75 and (ast >= 0.60 or token >= 0.55):
            score = max(score, 0.84)
            reasons.append("Submission is similar to a previous-semester case.")
        if token >= 0.70 and ast >= 0.65 and identifier_rename >= 0.55:
            score = max(score, 0.82)
            reasons.append("Same structure with renamed identifiers.")
        if ast >= 0.72 and (cfg >= 0.60 or dfg >= 0.60):
            score = max(score, 0.78)
            reasons.append("Structural and program-flow evidence agree.")
        if rare_pattern >= 0.70:
            score = max(score, score + 0.10)
            reasons.append("Shared rare implementation pattern.")
        if style_shift >= 0.75:
            score = max(score, min(0.72, score + 0.08))
            reasons.append(
                "Student style changed sharply; use only as supporting evidence."
            )

        concrete_support = sum(
            1 for key in self.concrete_keys if _get(normalized, key) >= 0.45
        )
        if embedding >= 0.75 and concrete_support == 0:
            score = min(score, 0.48)
            guardrails.append(
                "Capped result because embedding-only evidence cannot create high risk."
            )

        score = _clamp(score)
        confidence = self._confidence_label(score, concrete_support, reasons)
        professor_summary = self._summary(reasons, guardrails)

        return EvidenceRank(
            review_priority=round(score, 4),
            risk_score=round(score, 4),
            confidence=confidence,
            reasons=reasons
            or ["Evidence is mixed; review only if it appears in the top queue."],
            guardrails=guardrails,
            professor_summary=professor_summary,
            features=normalized,
        )

    def rank_cases(self, cases: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        """Attach ranker output to cases and sort by review priority descending."""
        ranked: List[Dict[str, Any]] = []
        for case in cases:
            features = case.get("features", {})
            rank = self.rank_pair(features, base_score=case.get("base_score"))
            enriched = dict(case)
            enriched["evidence_rank"] = rank
            enriched["review_priority"] = rank.review_priority
            ranked.append(enriched)
        return sorted(ranked, key=lambda item: item["review_priority"], reverse=True)

    def _confidence_label(
        self, score: float, concrete_support: int, reasons: List[str]
    ) -> str:
        """Translate score and evidence agreement into professor-facing confidence."""
        if score >= 0.82 and concrete_support >= 2 and reasons:
            return "High"
        if score >= 0.58 and concrete_support >= 1:
            return "Medium"
        return "Low"

    def _summary(self, reasons: List[str], guardrails: List[str]) -> str:
        """Build a concise natural-language explanation for review queues."""
        if reasons:
            return reasons[0]
        if guardrails:
            return "Shared regions were discounted before ranking this case."
        return "No single evidence layer is strong enough for high priority."
