"""Evidence Report - structured, auditable output from the layered pipeline.

Replaces the opaque fused score with a transparent report that answers "why did the system reach
this conclusion?". See ``EvidenceReport.to_dict`` for the output format.

Changes: ``requires_review`` now includes REVIEW (a verdict that says "human inspection required"
reported ``requires_review = False``); ``confidence`` and the fired ``decision_rule`` are part of
the report; there is ONE ``Verdict`` enum (the one in ``ehe``, which has FLAG) instead of two that
had to be mapped onto each other; and ``from_legacy_fusion`` no longer puts the whole fused score
into ``layer1_value`` (it fabricated deterministic-layer evidence) and maps MEDIUM to REVIEW
(it mapped it to FLAG, which means "semantic-only").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.backend.engines.detection.ehe import Verdict
from src.backend.engines.detection.layer1_deterministic import Layer1Result
from src.backend.engines.detection.layer2_statistical import Layer2Result
from src.backend.engines.detection.layer3_semantic import Layer3Result

try:
    from src.backend.engines.detection.layer4_explainability import ExplanationReport
except ImportError:
    ExplanationReport = None  # type: ignore[misc,assignment]

__all__ = ["EvidenceReport", "Verdict"]


def _num(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


@dataclass
class EvidenceReport:
    """Complete detection report. Every field can be traced to engine outputs and decision rules."""

    # --- Verdict ---
    verdict: Verdict
    decision_path: str  # e.g. "structural → statistical → semantic → strong_structural"
    explanation: str  # human-readable explanation of the decision

    # --- Per-layer values ---
    layer1_value: float = 0.0
    layer2_value: float = 0.0
    layer3_value: float = 0.0

    # --- Full evidence from each layer ---
    layer1_evidence: Layer1Result | None = None
    layer2_evidence: Layer2Result | None = None
    layer3_evidence: Layer3Result | None = None
    explanation_evidence: ExplanationReport | None = None  # Layer 4

    # --- Thresholds actually used by the decision engine ---
    thresholds: dict[str, Any] = field(default_factory=dict)

    # --- Decision metadata ---
    confidence: float = 0.0  # rule-based confidence of the fired rule (not a probability)
    decision_rule: str = ""  # id of the rule that fired

    # --- Additive risk score (compatibility with the existing UI) ---
    # NOT used for decision-making; the UI expects a single number.
    additive_score: float = 0.0

    @property
    def is_plagiarism(self) -> bool:
        """Whether the verdict indicates actionable plagiarism."""
        return self.verdict in (Verdict.TRUE, Verdict.PROBABLE)

    @property
    def requires_review(self) -> bool:
        """Whether a human has to look at this pair (everything except CLEAN)."""
        return self.verdict in (Verdict.TRUE, Verdict.PROBABLE, Verdict.REVIEW, Verdict.FLAG)

    @property
    def risk_level(self) -> str:
        """Risk level string for compatibility with the existing UI."""
        return {
            Verdict.TRUE: "CRITICAL",
            Verdict.PROBABLE: "HIGH",
            Verdict.REVIEW: "MEDIUM",
            Verdict.FLAG: "MEDIUM",
            Verdict.CLEAN: "LOW",
        }.get(self.verdict, "LOW")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        result: dict[str, Any] = {
            "verdict": Verdict(self.verdict).value,
            "decision_path": self.decision_path,
            "decision_rule": self.decision_rule,
            "explanation": self.explanation,
            "confidence": round(_num(self.confidence), 4),
            "is_plagiarism": self.is_plagiarism,
            "requires_review": self.requires_review,
            "risk_level": self.risk_level,
            "layer_values": {
                "layer1": round(_num(self.layer1_value), 4),
                "layer2": round(_num(self.layer2_value), 4),
                "layer3": round(_num(self.layer3_value), 4),
            },
            "thresholds": self.thresholds,
            "score": round(_num(self.additive_score), 4),
            "evidence": {},
        }
        if self.layer1_evidence:
            result["evidence"]["layer1"] = self.layer1_evidence.to_dict()
        if self.layer2_evidence:
            result["evidence"]["layer2"] = self.layer2_evidence.to_dict()
        if self.layer3_evidence:
            result["evidence"]["layer3"] = self.layer3_evidence.to_dict()
        if self.explanation_evidence:
            result["evidence"]["layer4"] = self.explanation_evidence.to_dict()
        return result

    def to_legacy_dict(self) -> dict[str, Any]:
        """Old-style flat dict (score, risk_level, features, contributions, fusion_debug)."""
        features: dict[str, Any] = {}
        if self.layer1_evidence:
            features.update(self.layer1_evidence.engine_scores)
        if self.layer2_evidence:
            features.update(self.layer2_evidence.engine_scores)
        if self.layer3_evidence:
            features.update(self.layer3_evidence.engine_scores)
        if self.explanation_evidence:
            features["layer4_plagiarism_type"] = self.explanation_evidence.plagiarism_type
            features["layer4_function_overlap_count"] = len(self.explanation_evidence.function_overlap)
            features["layer4_avg_function_similarity"] = self.explanation_evidence.avg_function_similarity

        features["layer1_confidence"] = self.layer1_value
        features["layer2_confidence"] = self.layer2_value
        features["layer3_confidence"] = self.layer3_value

        contributions = {
            "layer1_deterministic": self.layer1_value,
            "layer2_statistical": self.layer2_value,
            "layer3_semantic": self.layer3_value,
        }
        return {
            "score": round(_num(self.additive_score), 4),
            "risk_level": self.risk_level,
            "features": features,
            "contributions": {k: round(_num(v), 4) for k, v in contributions.items()},
            "fusion_debug": {
                "method": "evidence_hierarchy",
                "decision_path": self.decision_path,
                "decision_rule": self.decision_rule,
                "explanation": self.explanation,
                "confidence": round(_num(self.confidence), 4),
                "verdict": Verdict(self.verdict).value,
                "thresholds": self.thresholds,
                "layer_values": {
                    "layer1": round(_num(self.layer1_value), 4),
                    "layer2": round(_num(self.layer2_value), 4),
                    "layer3": round(_num(self.layer3_value), 4),
                },
            },
        }

    @classmethod
    def from_legacy_fusion(cls, score: float, risk_level: str, features: dict[str, float]) -> EvidenceReport:
        """Create an EvidenceReport from legacy fusion output (migration only).

        The legacy score is kept as ``additive_score``; the layer values stay 0.0 because the
        legacy engine produced no per-layer evidence.
        """
        verdict_map = {
            "CRITICAL": Verdict.TRUE,
            "HIGH": Verdict.PROBABLE,
            "MEDIUM": Verdict.REVIEW,  # (was FLAG, which means "semantic-only")
            "LOW": Verdict.CLEAN,
        }
        verdict = verdict_map.get(str(risk_level).upper(), Verdict.CLEAN)
        score = min(1.0, max(0.0, _num(score)))
        return cls(
            verdict=verdict,
            decision_path="legacy_fusion_fallback",
            decision_rule="legacy_fusion_fallback",
            explanation=(
                f"Produced via the legacy weighted-fusion engine. Final score: {score:.1%}, "
                f"risk: {risk_level}. Consider migrating to the layered pipeline."
            ),
            thresholds={"default_threshold": 0.5},
            additive_score=score,
        )
