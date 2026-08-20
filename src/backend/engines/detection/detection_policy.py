"""Detection Policy — Rule-based decision tree using Evidence Hierarchy Engine.

This module integrates the Evidence Hierarchy Engine (EHE) for hierarchical
decision making that eliminates score pollution and ensures deterministic verdicts.

Key improvements over v1:
  - Uses EHE for hierarchical evidence processing
  - Identity evidence hard-stops the pipeline
  - Structural evidence dominates semantic evidence
  - No weighted averaging across evidence types
  - Full audit trail for every decision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.backend.engines.detection.ehe import (
    EvidenceHierarchyEngine,
)
from src.backend.engines.detection.evidence_report import EvidenceReport, Verdict
from src.backend.engines.detection.layer1_deterministic import Layer1Result
from src.backend.engines.detection.layer2_statistical import Layer2Result
from src.backend.engines.detection.layer3_semantic import Layer3Result
from src.backend.engines.detection.layer4_explainability import ExplanationReport

logger = logging.getLogger(__name__)

# Default config path for detection policy
DETECTION_POLICY_CONFIG_PATH = Path(__file__).parent / "detection_policy.yaml"


@dataclass
class DecisionThresholds:
    """Configurable thresholds for the decision tree.

    Every threshold has a clear semantic meaning — no black-box weights.
    """

    # ─── Layer 1: Deterministic (hard match) ──────────────────────────────
    hard_match_threshold: float = 0.90  # L1 ≥ 0.90 → TRUE (conclusive)
    high_confidence_l1: float = 0.85  # L1 ≥ 0.85 AND L2 ≥ 0.85 → TRUE
    high_confidence_l2: float = 0.85  # (fixes the "L1=0.89 gap")
    strong_structural_l1: float = 0.70  # L1 ≥ 0.70 AND L2 ≥ 0.60 → TRUE
    strong_structural_l2: float = 0.60

    # ─── Layer 2: Statistical ──────────────────────────────────────────────
    probable_l2: float = 0.80  # L2 ≥ 0.80 AND L3 ≥ 0.80 → PROBABLE
    probable_l3: float = 0.80
    review_l2_threshold: float = 0.50  # L2 ≥ 0.50 → REVIEW zone

    # ─── Layer 3: Semantic (review only, NEVER standalone verdict) ────────
    flag_l3_threshold: float = 0.90  # L3 ≥ 0.90 → FLAG (must review)

    # ─── Review zone (human review needed) ─────────────────────────────────
    review_l1_threshold: float = 0.50  # L1 ≥ 0.50 → REVIEW
    review_enabled: bool = True  # Enable/disable REVIEW verdict

    # ─── Course-specific multipliers ───────────────────────────────────────
    cs_code_ast_weight: float = 1.2  # CS courses: AST is king
    essay_semantic_weight: float = 1.5  # Essays: semantic matters more
    math_structure_weight: float = 1.3  # Math: formula structure

    def to_dict(self) -> dict[str, float]:
        return {
            "hard_match_threshold": self.hard_match_threshold,
            "high_confidence_l1": self.high_confidence_l1,
            "high_confidence_l2": self.high_confidence_l2,
            "strong_structural_l1": self.strong_structural_l1,
            "strong_structural_l2": self.strong_structural_l2,
            "probable_l2": self.probable_l2,
            "probable_l3": self.probable_l3,
            "flag_l3_threshold": self.flag_l3_threshold,
            "review_l1_threshold": self.review_l1_threshold,
            "review_l2_threshold": self.review_l2_threshold,
            "review_enabled": self.review_enabled,
            "cs_code_ast_weight": self.cs_code_ast_weight,
            "essay_semantic_weight": self.essay_semantic_weight,
            "math_structure_weight": self.math_structure_weight,
        }


def _load_policy_config() -> dict[str, Any]:
    """Load detection policy from YAML config file."""
    if not DETECTION_POLICY_CONFIG_PATH.exists():
        return {}

    try:
        with open(DETECTION_POLICY_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        logger.warning("Failed to load detection policy config, using defaults")
        return {}


def default_thresholds(domain: str = "code") -> DecisionThresholds:
    """Return default thresholds, optionally adjusted for a domain."""
    base = DecisionThresholds()
    if domain == "essay":
        # Essays: semantic plays a larger role, structural less
        base.flag_l3_threshold = 0.85
        base.strong_structural_l1 = 0.65
        base.probable_l2 = 0.75
    elif domain == "math":
        # Math: structure-based evidence is more reliable
        base.strong_structural_l1 = 0.65
        base.strong_structural_l2 = 0.55
    elif domain == "cs_code":
        # CS code: AST is most reliable, semantic is supplementary
        pass  # course multiplier handles this
    return base


# ═══════════════════════════════════════════════════════════════════════════
# FIX 1: Layer 1 uses max(), NOT weighted average
# ═══════════════════════════════════════════════════════════════════════════
def _compute_layer1_value(l1: Layer1Result, domain: str = "code") -> float:
    """Compute Layer 1 confidence using max-of-best, NOT weighted average.

    Fix: Previously used ast*0.4 + token*0.25 + ... which diluted
    strong single-engine signals (e.g. AST=0.85 → L1=0.69).

    Now: L1 = max(exact_match, structural, token, winnowing)
    The strongest evidence wins — no dilution.
    """
    # Exact match is always conclusive
    if l1.has_exact_file_match:
        return 1.0
    if l1.exact_match_score >= 0.90:
        return l1.exact_match_score

    # Evidence-based: strongest deterministic signal wins
    candidates = [
        l1.ast_subtree_overlap,  # AST structural match
        l1.ast_node_match,  # AST node-type match
        l1.structural_similarity,  # Combined structural signal
        l1.token_overlap,  # Token overlap
        l1.winnowing_overlap,  # Winnowing fingerprint
        l1.ngram_overlap,  # N-gram sequence match
    ]

    # Domain-specific boost for AST (CS code) or structure (math)
    domain_boost = 1.0
    if domain == "cs_code":
        domain_boost = 1.2  # AST is most reliable for CS code
        # Boost AST candidates
        candidates[0] = min(1.0, l1.ast_subtree_overlap * domain_boost)
        candidates[1] = min(1.0, l1.ast_node_match * domain_boost)
    elif domain == "math":
        domain_boost = 1.3  # Structure is most reliable for math
        candidates[2] = min(1.0, l1.structural_similarity * domain_boost)

    return max(candidates)


# ═══════════════════════════════════════════════════════════════════════════
# Layer 2: max() — strongest statistical signal wins
# ═══════════════════════════════════════════════════════════════════════════
def _compute_layer2_value(l2: Layer2Result) -> float:
    """Compute Layer 2 confidence using max, not average.

    Fix: Previously used graph*0.30 + logic_flow*0.25 + ... which
    diluted evidence. Now the strongest signal wins.
    """
    candidates = [
        l2.graph_similarity,  # CFG/execution structure
        l2.logic_flow_similarity,  # Control+operator flow
        1.0 - l2.stylometric_distance,  # Style closeness (inverted)
        l2.sentence_structure_similarity,  # Structural profile
        l2.control_flow_match,  # Control flow match
        l2.data_flow_match,  # Data flow match
    ]
    return max(candidates)


# ═══════════════════════════════════════════════════════════════════════════
# Layer 3: max() with cap — semantic evidence, deliberately constrained
# ═══════════════════════════════════════════════════════════════════════════
def _compute_layer3_value(l3: Layer3Result) -> float:
    """Compute Layer 3 confidence using max, capped at 0.95.

    Embedding similarity is ALREADY baseline-corrected and capped
    in Layer3Semantic.evaluate() so we trust the corrected values.
    """
    candidates = [
        l3.embedding_similarity,  # Baseline-corrected embedding
        l3.transformer_score,  # Transformer encoder score
        l3.concept_overlap_score,  # Concept/topic overlap
        l3.semantic_similarity_score,  # Combined semantic score
    ]
    # Hard cap: semantic alone can never exceed 0.95
    return min(0.95, max(candidates))


def _explain_decision_path(
    verdict: Verdict,
    l1_val: float,
    l2_val: float,
    l3_val: float,
    thresholds: DecisionThresholds,
) -> str:
    """Generate a human-readable explanation of the decision path.

    Every explanation includes the exact rule that triggered and
    the evidence that led to it. Audit-friendly.
    """
    if verdict == Verdict.TRUE:
        if l1_val >= thresholds.hard_match_threshold:
            return (
                f"Hard Match: Layer 1 = {l1_val:.0%} ≥ {thresholds.hard_match_threshold:.0%}. "
                f"AST/token/winnowing evidence is conclusive — no semantic signal needed."
            )
        elif (
            l1_val >= thresholds.high_confidence_l1
            and l2_val >= thresholds.high_confidence_l2
        ):
            return (
                f"High-Confidence Combined: Layer 1 = {l1_val:.0%} AND "
                f"Layer 2 = {l2_val:.0%} ≥ {thresholds.high_confidence_l2:.0%}. "
                f"Deterministic + statistical evidence both very strong."
            )
        elif (
            l1_val >= thresholds.strong_structural_l1
            and l2_val >= thresholds.strong_structural_l2
        ):
            return (
                f"Strong Structural: Layer 1 = {l1_val:.0%} ≥ {thresholds.strong_structural_l1:.0%} AND "
                f"Layer 2 = {l2_val:.0%} ≥ {thresholds.strong_structural_l2:.0%}. "
                f"Structural and statistical evidence confirms plagiarism."
            )
        return "TRUE by combined evidence across all three layers."

    elif verdict == Verdict.PROBABLE:
        return (
            f"Probable: Layer 2 = {l2_val:.0%} ≥ {thresholds.probable_l2:.0%} AND "
            f"Layer 3 = {l3_val:.0%} ≥ {thresholds.probable_l3:.0%}. "
            f"Structural + semantic patterns suggest plagiarism — needs manual review."
        )

    elif verdict == Verdict.FLAG:
        return (
            f"Semantic Flag: Layer 3 = {l3_val:.0%} ≥ {thresholds.flag_l3_threshold:.0%} "
            f"but Layers 1 and 2 are inconclusive. "
            f"High semantic similarity alone — manual review REQUIRED, high false-positive risk."
        )

    elif verdict == Verdict.REVIEW:
        return (
            f"Review Zone: L1={l1_val:.0%}, L2={l2_val:.0%}. "
            f"Borderline signals detected — too weak for automated action, "
            f"too strong to ignore. Manual inspection recommended."
        )

    else:  # CLEAN
        return (
            f"Clean: L1={l1_val:.0%}, L2={l2_val:.0%}, L3={l3_val:.0%}. "
            f"All layers below minimum thresholds — no evidence of plagiarism."
        )


class DetectionPolicy:
    """Rule-based detection policy using Evidence Hierarchy Engine.

    Delegates to EHE for hierarchical evidence processing with
    strict priority ordering: Identity > Structural > Statistical > Semantic.
    """

    def __init__(
        self,
        thresholds: DecisionThresholds | None = None,
        domain: str = "code",
    ):
        config = _load_policy_config()
        self.thresholds = thresholds or default_thresholds(domain)
        self.domain = domain
        self.ehe = EvidenceHierarchyEngine()

        # Apply course-specific overrides from config
        config_thresholds = config.get("thresholds", {})
        if config_thresholds:
            for field_name in self.thresholds.to_dict():
                if field_name in config_thresholds:
                    setattr(
                        self.thresholds,
                        field_name,
                        float(config_thresholds[field_name]),
                    )

    def evaluate(
        self,
        l1_result: Layer1Result,
        l2_result: Layer2Result,
        l3_result: Layer3Result,
        course_type: str | None = None,
        explanation_report: ExplanationReport | None = None,
    ) -> EvidenceReport:
        """Run the decision tree using Evidence Hierarchy Engine.

        Args:
            l1_result: Output from Layer1Deterministic.
            l2_result: Output from Layer2Statistical.
            l3_result: Output from Layer3Semantic.
            course_type: Optional course type hint ('cs_code', 'essay', 'math', etc.)
            explanation_report: Optional explanation report from Layer 4.

        Returns:
            EvidenceReport with verdict, decision path, and full evidence.
        """
        domain = course_type or self.domain

        # Compute per-layer values (max-based, no dilution)
        l1_val = _compute_layer1_value(l1_result, domain)
        l2_val = _compute_layer2_value(l2_result)
        l3_val = _compute_layer3_value(l3_result)

        # Build engine scores for EHE
        engine_scores = {
            "ast": l1_result.engine_scores.get("ast", 0.0),
            "token": l1_result.engine_scores.get("token", 0.0),
            "winnowing": l1_result.engine_scores.get("winnowing", 0.0),
            "ngram": l1_result.engine_scores.get("ngram", 0.0),
            "logic_flow": l2_result.engine_scores.get("logic_flow", 0.0),
            "graph": l2_result.engine_scores.get("graph", 0.0),
            "stylometry": 1.0 - l2_result.stylometric_distance,
            "embedding": l3_result.engine_scores.get("embedding", 0.0),
        }

        # Build evidence dict for EHE
        {
            "layer1": l1_result.to_dict(),
            "layer2": l2_result.to_dict(),
            "layer3": l3_result.to_dict(),
        }

        # Check for exact file match (hard override)
        if l1_result.has_exact_file_match:
            engine_scores["exact_match"] = True

        # Run EHE decision
        ehe_decision = self.ehe.decide(
            code_a="", code_b="", engine_scores=engine_scores
        )

        # Map EHE verdict to Verdict enum
        verdict_map = {
            "TRUE": Verdict.TRUE,
            "PROBABLE": Verdict.PROBABLE,
            "REVIEW": Verdict.REVIEW,
            "CLEAN": Verdict.CLEAN,
        }
        verdict = verdict_map.get(ehe_decision.verdict, Verdict.CLEAN)

        # Build explanation
        explanation = self._build_explanation(ehe_decision, l1_val, l2_val, l3_val)

        # Include Layer 4 evidence if available
        if explanation_report:
            explanation += "\n\n" + explanation_report.summary()

        return EvidenceReport(
            verdict=verdict,
            decision_path=" → ".join(ehe_decision.decision_path),
            layer1_value=round(l1_val, 4),
            layer2_value=round(l2_val, 4),
            layer3_value=round(l3_val, 4),
            explanation=explanation,
            layer1_evidence=l1_result,
            layer2_evidence=l2_result,
            layer3_evidence=l3_result,
            explanation_evidence=explanation_report,
            thresholds=self.thresholds.to_dict(),
        )

    def _build_explanation(
        self,
        ehe_decision: Any,
        l1_val: float,
        l2_val: float,
        l3_val: float,
    ) -> str:
        """Build human-readable explanation for EHE decision."""
        if ehe_decision.verdict == "TRUE":
            if "identity_override" in ehe_decision.decision_path:
                return "Identity override: Files are identical."
            return f"Strong evidence detected (L1={l1_val:.0%}, L2={l2_val:.0%})."
        elif ehe_decision.verdict == "PROBABLE":
            return f"Probable plagiarism (L2={l2_val:.0%}, L3={l3_val:.0%})."
        elif ehe_decision.verdict == "REVIEW":
            return f"Borderline signals detected (L1={l1_val:.0%}, L2={l2_val:.0%}). Human review required."
        else:
            return f"No significant similarity detected (L1={l1_val:.0%}, L2={l2_val:.0%})."

    def get_thresholds(self) -> dict[str, float]:
        """Return current decision thresholds (for display/settings)."""
        return self.thresholds.to_dict()

    @classmethod
    def available_domains(cls) -> dict[str, str]:
        """Return available domain presets."""
        return {
            "code": "General code plagiarism detection (balanced)",
            "cs_code": "CS programming assignments (AST-weighted, structural evidence dominant)",
            "essay": "Essay/report similarity (semantic-weighted, broader review zone)",
            "math": "Mathematics proofs (structure-weighted, formula/graph emphasis)",
        }
