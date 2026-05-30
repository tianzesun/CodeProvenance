"""Policy-only Decision Layer for Evidence Hierarchy Engine.

=============================================================================
DETERMINISTIC EVIDENCE PRINCIPLE
=============================================================================

This is the core architectural principle for the rule-based evidence system:

1. NO AVERAGING for decision making
   - Decisions are rule-triggered, not score-derived
   - Do NOT compute mean/median/weighted scores for verdicts

2. IDENTITY overrides all signals
   - Exact match (fingerprint >= 0.95) → TRUE immediately
   - No further processing allowed

3. STRUCTURAL dominance required for plagiarism
   - structural >= 0.60 is minimum threshold
   - semantic dominance requires structural support

4. WEAK signals cannot accumulate
   - Single engine high score does NOT create TRUE verdict
   - Requires corroborating evidence

5. OUTPUT must be rule-triggered
   - VERDICT: CLEAN | REVIEW | PROBABLE | TRUE
   - CONFIDENCE: rule-based (not averaged)
   - REASON: triggered rule
   - EVIDENCE: per-layer signals

This system converges to:
    Input → Evidence → Rule → Verdict
    (stable)  (fixed)  (policy)  (deterministic)

=============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.backend.engines.evidence_aggregator import EvidenceVector


@dataclass
class Decision:
    """Deterministic decision output from policy evaluation."""

    verdict: str  # CLEAN, REVIEW, PROBABLE, TRUE
    confidence: float  # Rule-based confidence (0.0-1.0)
    evidence: Dict[str, float]
    reason: str = ""
    triggered_layer: str = ""


class DecisionPolicy:
    """
    Policy-only decision engine.

    Rules are evaluated in strict priority order.
    First matching rule wins.

    CRITICAL: NO score averaging or fusion is performed.
    Decisions are purely rule-based.
    """

    @staticmethod
    def decide(evidence: EvidenceVector) -> Decision:
        """
        Apply deterministic rules to evidence.

        Args:
            evidence: EvidenceVector with structural, lexical, semantic, style scores

        Returns:
            Decision with verdict, confidence, evidence, and reason
        """
        # Rule 0: Identity Override (exact match handled upstream)
        # This rule is for documentation - actual identity check is in hard_gate

        # Rule 1: Stability Guard - CRITICAL for preventing false positives
        # If max structural evidence is weak, return CLEAN regardless of other signals
        if evidence.structural < 0.60:
            return Decision(
                verdict="CLEAN",
                confidence=0.95,
                evidence=evidence.to_dict(),
                reason="stability_guard_no_structural_evidence",
                triggered_layer="structural",
            )

        # Rule 2: Strong Structural Evidence with Multiple Signals
        # REQUIRES: structural >= 0.90 AND (lexical >= 0.50 OR semantic >= 0.50)
        # This prevents single-engine false positives
        if evidence.structural >= 0.90 and (
            evidence.lexical >= 0.50 or evidence.semantic >= 0.50
        ):
            return Decision(
                verdict="TRUE",
                confidence=0.95,
                evidence=evidence.to_dict(),
                reason="strong_structural_with_supporting_evidence",
                triggered_layer="structural",
            )

        # Rule 3: Semantic Dominance - Strong embedding with structural support
        if evidence.semantic >= 0.95 and evidence.structural >= 0.50:
            return Decision(
                verdict="PROBABLE",
                confidence=0.85,
                evidence=evidence.to_dict(),
                reason="semantic_dominance_with_structural_support",
                triggered_layer="semantic",
            )

        # Rule 4: Medium Structural + Lexical Support
        if evidence.structural >= 0.75 and evidence.lexical >= 0.50:
            return Decision(
                verdict="PROBABLE",
                confidence=0.80,
                evidence=evidence.to_dict(),
                reason="medium_structural_lexical_support",
                triggered_layer="structural",
            )

        # Rule 5: Moderate Structural + Strong Style
        if evidence.structural >= 0.50 and evidence.style >= 0.70:
            return Decision(
                verdict="PROBABLE",
                confidence=0.75,
                evidence=evidence.to_dict(),
                reason="moderate_structural_strong_style",
                triggered_layer="structural_style",
            )

        # Rule 6: Semantic Only - Requires review (never auto-TRUE)
        if evidence.semantic >= 0.85 and evidence.structural < 0.50:
            return Decision(
                verdict="REVIEW",
                confidence=0.60,
                evidence=evidence.to_dict(),
                reason="semantic_only_requires_review",
                triggered_layer="semantic",
            )

        # Rule 7: Borderline Signals
        if (
            evidence.structural >= 0.30
            or evidence.lexical >= 0.30
            or evidence.semantic >= 0.30
        ):
            return Decision(
                verdict="REVIEW",
                confidence=0.40,
                evidence=evidence.to_dict(),
                reason="borderline_signals",
                triggered_layer="borderline",
            )

        # Rule 8: Clean - No evidence
        return Decision(
            verdict="CLEAN",
            confidence=0.95,
            evidence=evidence.to_dict(),
            reason="clean_no_evidence",
            triggered_layer="none",
        )
