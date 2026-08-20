"""Evidence Report — Structured, auditable output from the three-layer pipeline.

Replaces the opaque fused score with a transparent evidence report that
answers "why did the system reach this conclusion?" directly.

Output format:
```json
{
  "verdict": "TRUE",
  "decision_path": "hard_match",
  "explanation": "Layer 1 = 92% >= 90%: Hard match...",
  "confidence": 0.92,
  "evidence": {
    "layer1": { "exact_match_score": 0.85, "ast_subtree_overlap": 0.78, ... },
    "layer2": { "graph_similarity": 0.72, "logic_flow_similarity": 0.65, ... },
    "layer3": { "embedding_similarity": 0.45, ... }
  },
  "thresholds": { "hard_match_threshold": 0.90, ... }
}
```
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

from src.backend.engines.detection.layer1_deterministic import Layer1Result
from src.backend.engines.detection.layer2_statistical import Layer2Result
from src.backend.engines.detection.layer3_semantic import Layer3Result

try:
    from src.backend.engines.detection.layer4_explainability import ExplanationReport
except ImportError:
    ExplanationReport = None  # type: ignore[misc]


class Verdict(Enum):
    """Final detection verdict from the three-layer pipeline.

    Verdict hierarchy (from most to least actionable):
      TRUE     → Definite plagiarism — actionable evidence chain
      PROBABLE → Likely plagiarism — needs manual review
      REVIEW   → Borderline — human inspection required (was CLEAN in v1)
      FLAG     → Semantic-only flag — review required, high false-positive risk
      CLEAN    → No evidence of plagiarism
    """

    TRUE = "TRUE"
    PROBABLE = "PROBABLE"
    REVIEW = "REVIEW"
    FLAG = "FLAG"
    CLEAN = "CLEAN"


@dataclass
class EvidenceReport:
    """Complete detection report from the three-layer pipeline.

    This is the primary output object. Every field is auditable and
    can be traced back to specific engine outputs and decision rules.
    """

    # --- Verdict ---
    verdict: Verdict
    decision_path: str  # e.g. "hard_match" -> "l1>=90%"
    explanation: str  # Human-readable explanation of the decision

    # --- Per-layer values ---
    layer1_value: float = 0.0
    layer2_value: float = 0.0
    layer3_value: float = 0.0

    # --- Full evidence from each layer ---
    layer1_evidence: Optional[Layer1Result] = None
    layer2_evidence: Optional[Layer2Result] = None
    layer3_evidence: Optional[Layer3Result] = None
    explanation_evidence: Optional["ExplanationReport"] = None  # Layer 4

    # --- Current thresholds used ---
    thresholds: Dict[str, float] = field(default_factory=dict)

    # --- Additive risk score (for compatibility with existing UI) ---
    # This is NOT used for decision-making — it's provided for the
    # existing benchmark/report UI that expects a single score value.
    additive_score: float = 0.0

    @property
    def is_plagiarism(self) -> bool:
        """Whether the verdict indicates actionable plagiarism."""
        return self.verdict in (Verdict.TRUE, Verdict.PROBABLE)

    @property
    def requires_review(self) -> bool:
        """Whether this pair needs human review."""
        return self.verdict in (Verdict.TRUE, Verdict.PROBABLE, Verdict.FLAG)

    @property
    def risk_level(self) -> str:
        """Risk level string for compatibility with existing UI."""
        return {
            Verdict.TRUE: "CRITICAL",
            Verdict.PROBABLE: "HIGH",
            Verdict.REVIEW: "MEDIUM",
            Verdict.FLAG: "MEDIUM",
            Verdict.CLEAN: "LOW",
        }.get(self.verdict, "LOW")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result = {
            "verdict": self.verdict.value,
            "decision_path": self.decision_path,
            "explanation": self.explanation,
            "is_plagiarism": self.is_plagiarism,
            "requires_review": self.requires_review,
            "risk_level": self.risk_level,
            "layer_values": {
                "layer1": round(self.layer1_value, 4),
                "layer2": round(self.layer2_value, 4),
                "layer3": round(self.layer3_value, 4),
            },
            "thresholds": self.thresholds,
            "score": round(self.additive_score, 4),
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

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Convert to legacy format for backward compatibility.

        Returns the old-style flat dict with score, risk_level, features, etc.
        """
        features = {}
        if self.layer1_evidence:
            features.update(self.layer1_evidence.engine_scores)
        if self.layer2_evidence:
            features.update(self.layer2_evidence.engine_scores)
        if self.layer3_evidence:
            features.update(self.layer3_evidence.engine_scores)
        if self.explanation_evidence:
            features["layer4_plagiarism_type"] = (
                self.explanation_evidence.plagiarism_type
            )
            features["layer4_function_overlap_count"] = len(
                self.explanation_evidence.function_overlap
            )
            features["layer4_avg_function_similarity"] = (
                self.explanation_evidence.avg_function_similarity
            )

        # Add layer values as features for debugging
        features["layer1_confidence"] = self.layer1_value
        features["layer2_confidence"] = self.layer2_value
        features["layer3_confidence"] = self.layer3_value

        contributions = {
            "layer1_deterministic": self.layer1_value,
            "layer2_statistical": self.layer2_value,
            "layer3_semantic": self.layer3_value,
        }

        return {
            "score": round(self.additive_score, 4),
            "risk_level": self.risk_level,
            "features": features,
            "contributions": {k: round(v, 4) for k, v in contributions.items()},
            "fusion_debug": {
                "method": "three_layer_decision_tree",
                "decision_path": self.decision_path,
                "explanation": self.explanation,
                "verdict": (
                    self.verdict.value
                    if hasattr(self.verdict, "value")
                    else str(self.verdict)
                ),
                "thresholds": self.thresholds,
                "layer_values": {
                    "layer1": round(self.layer1_value, 4),
                    "layer2": round(self.layer2_value, 4),
                    "layer3": round(self.layer3_value, 4),
                },
            },
        }

    @classmethod
    def from_legacy_fusion(
        cls,
        score: float,
        risk_level: str,
        features: Dict[str, float],
    ) -> "EvidenceReport":
        """Create an EvidenceReport from legacy fusion output (for migration)."""
        # Map legacy risk level back to verdict
        verdict_map = {
            "CRITICAL": Verdict.TRUE,
            "HIGH": Verdict.PROBABLE,
            "MEDIUM": Verdict.FLAG,
            "LOW": Verdict.CLEAN,
        }
        verdict = verdict_map.get(risk_level.upper(), Verdict.CLEAN)

        report = cls(
            verdict=verdict,
            decision_path="legacy_fusion_fallback",
            explanation=(
                f"Produced via legacy weighted-fusion engine. "
                f"Final score: {score:.1%}, risk: {risk_level}. "
                f"Consider migrating to the three-layer pipeline."
            ),
            layer1_value=score,
            thresholds={"default_threshold": 0.5},
            additive_score=score,
        )
        return report
