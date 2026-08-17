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
    def _calibrated_confidence(verdict: str, evidence: EvidenceVector) -> float:
        """Return a monotone, continuous confidence for a verdict band.

        Each verdict maps to a non-overlapping value band, interpolated by the
        strongest evidence signal.  This fixes two past defects: clean pairs
        were assigned the same confidence as TRUE hits, and the fixed rule
        constants could not rank by evidence strength.

        Returns:
            A float in [0.05, 1.0], monotone in evidence strength.
        """
        strength = min(
            1.0,
            max(
                evidence.structural,
                evidence.lexical,
                evidence.semantic,
                evidence.style,
                evidence.coverage,
            ),
        )
        bands = {
            "CLEAN": (0.05, 0.35),
            "PROBABLE": (0.70, 0.85),
            "REVIEW": (0.40, 0.70),
            "TRUE": (0.85, 1.00),
        }
        low, high = bands[verdict]
        return round(low + (high - low) * strength, 4)

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
                confidence=DecisionPolicy._calibrated_confidence("CLEAN", evidence),
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
                confidence=DecisionPolicy._calibrated_confidence("TRUE", evidence),
                evidence=evidence.to_dict(),
                reason="strong_structural_with_supporting_evidence",
                triggered_layer="structural",
            )

        # Rule 3: Semantic Dominance - Strong embedding with structural support
        if evidence.semantic >= 0.95 and evidence.structural >= 0.50:
            return Decision(
                verdict="PROBABLE",
                confidence=DecisionPolicy._calibrated_confidence("PROBABLE", evidence),
                evidence=evidence.to_dict(),
                reason="semantic_dominance_with_structural_support",
                triggered_layer="semantic",
            )

        # Rule 4: Medium Structural + Lexical Support
        if evidence.structural >= 0.75 and evidence.lexical >= 0.50:
            return Decision(
                verdict="PROBABLE",
                confidence=DecisionPolicy._calibrated_confidence("PROBABLE", evidence),
                evidence=evidence.to_dict(),
                reason="medium_structural_lexical_support",
                triggered_layer="structural",
            )

        # Rule 5: Moderate Structural + Strong Style
        if evidence.structural >= 0.50 and evidence.style >= 0.70:
            return Decision(
                verdict="PROBABLE",
                confidence=DecisionPolicy._calibrated_confidence("PROBABLE", evidence),
                evidence=evidence.to_dict(),
                reason="moderate_structural_strong_style",
                triggered_layer="structural_style",
            )

        # Rule 6: AST-only structural — AST is supporting-only, never decisive alone
        # If structural is high but no other evidence dimension corroborates,
        # the high score may be driven solely by AST structural patterns
        # (e.g. similar control flow in boilerplate code). Downgrade to REVIEW.
        if (
            evidence.structural >= 0.70
            and evidence.lexical < 0.40
            and evidence.semantic < 0.40
            and evidence.style < 0.40
        ):
            return Decision(
                verdict="REVIEW",
                confidence=DecisionPolicy._calibrated_confidence("REVIEW", evidence),
                evidence=evidence.to_dict(),
                reason="ast_only_structural_no_corroboration",
                triggered_layer="ast",
            )

        # Rule 7: Semantic Only - Requires review (never auto-TRUE)
        if evidence.semantic >= 0.85 and evidence.structural < 0.50:
            return Decision(
                verdict="REVIEW",
                confidence=DecisionPolicy._calibrated_confidence("REVIEW", evidence),
                evidence=evidence.to_dict(),
                reason="semantic_only_requires_review",
                triggered_layer="semantic",
            )

        # Rule 8: Borderline Signals
        if (
            evidence.structural >= 0.30
            or evidence.lexical >= 0.30
            or evidence.semantic >= 0.30
        ):
            return Decision(
                verdict="REVIEW",
                confidence=DecisionPolicy._calibrated_confidence("REVIEW", evidence),
                evidence=evidence.to_dict(),
                reason="borderline_signals",
                triggered_layer="borderline",
            )

        # Rule 9: Clean - No evidence
        return Decision(
            verdict="CLEAN",
            confidence=DecisionPolicy._calibrated_confidence("CLEAN", evidence),
            evidence=evidence.to_dict(),
            reason="clean_no_evidence",
            triggered_layer="none",
        )
