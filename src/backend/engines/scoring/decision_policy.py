"""Policy-only Decision Layer for Evidence Hierarchy Engine.

This module implements deterministic rules for verdict decisions.
NO score fusion or averaging is performed here - only policy evaluation.

Output format:
    VERDICT: CLEAN | REVIEW | PROBABLE | TRUE
    CONFIDENCE: rule-based confidence
    EVIDENCE: per-layer signals
    REASON: triggered rule
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Decision:
    """Deterministic decision output from policy evaluation."""

    verdict: str  # CLEAN, REVIEW, PROBABLE, TRUE
    confidence: float  # Rule-based confidence (0.0-1.0)
    evidence: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    triggered_layer: str = ""


class DecisionPolicy:
    """
    Policy-only decision engine.

    Rules are evaluated in strict priority order.
    First matching rule wins.
    """

    @staticmethod
    def decide(evidence: dict[str, float]) -> Decision:
        """
        Apply deterministic rules to evidence.

        Args:
            evidence: Dictionary with keys:
                - identity: 1.0 if exact/hash match, else 0.0
                - structural: max structural signal
                - statistical: max statistical signal
                - semantic: embedding score
                - logic_flow: control flow similarity
                - fingerprint: token similarity

        Returns:
            Decision with verdict, confidence, evidence, and reason
        """
        # Rule 0: Identity Override (HARD STOP)
        if evidence.get("identity", 0.0) >= 1.0:
            return Decision(
                verdict="TRUE",
                confidence=1.0,
                evidence={"identity": evidence},
                reason="identity_override",
                triggered_layer="identity",
            )

        # Rule 1: Stability Guard - Require minimum structural evidence
        # If max structural signal is weak, consider clean regardless of other signals
        structural = evidence.get("structural", 0.0)
        logic_flow = evidence.get("logic_flow", 0.0)
        fingerprint = evidence.get("fingerprint", 0.0)

        max_structural = max(structural, logic_flow, fingerprint)
        if max_structural < 0.50:
            return Decision(
                verdict="CLEAN",
                confidence=0.95,
                evidence={
                    "structural": evidence.get("structural", 0),
                    "logic_flow": logic_flow,
                    "fingerprint": fingerprint,
                },
                reason="stability_guard_no_structural_evidence",
                triggered_layer="structural",
            )

        # Rule 2: Strong Structural - High confidence TRUE
        if max_structural >= 0.90:
            return Decision(
                verdict="TRUE",
                confidence=0.95,
                evidence={
                    "structural": structural,
                    "logic_flow": logic_flow,
                    "fingerprint": fingerprint,
                },
                reason="strong_structural_evidence",
                triggered_layer="structural",
            )

        # Rule 3: Semantic Dominance - Strong embedding overrides weak structural
        semantic = evidence.get("semantic", 0.0)
        if semantic >= 0.95 and max_structural >= 0.50:
            return Decision(
                verdict="PROBABLE",
                confidence=0.85,
                evidence={
                    "structural": structural,
                    "statistical": evidence.get("statistical", 0),
                    "semantic": semantic,
                },
                reason="semantic_dominance_with_structural_support",
                triggered_layer="semantic",
            )

        # Rule 4: Medium Structural + Statistical Support
        if max_structural >= 0.75:
            return Decision(
                verdict="PROBABLE",
                confidence=0.80,
                evidence={
                    "structural": structural,
                    "statistical": evidence.get("statistical", 0),
                },
                reason="medium_structural_with_support",
                triggered_layer="structural",
            )

        # Rule 5: Moderate Structural + Strong Statistical
        statistical = evidence.get("statistical", 0.0)
        if max_structural >= 0.50 and statistical >= 0.70:
            return Decision(
                verdict="PROBABLE",
                confidence=0.75,
                evidence={"structural": structural, "statistical": statistical},
                reason="moderate_structural_strong_statistical",
                triggered_layer="structural_statistical",
            )

        # Rule 6: Semantic Only - Requires review (never auto-TRUE)
        if semantic >= 0.85 and max_structural < 0.50:
            return Decision(
                verdict="REVIEW",
                confidence=0.60,
                evidence={
                    "structural": structural,
                    "statistical": statistical,
                    "semantic": semantic,
                },
                reason="semantic_only_warning",
                triggered_layer="semantic",
            )

        # Rule 7: Borderline Signals
        if max_structural >= 0.30 or statistical >= 0.30 or semantic >= 0.30:
            return Decision(
                verdict="REVIEW",
                confidence=0.40,
                evidence={
                    "structural": structural,
                    "statistical": statistical,
                    "semantic": semantic,
                },
                reason="borderline_signals",
                triggered_layer="borderline",
            )

        # Rule 8: Clean - No evidence
        return Decision(
            verdict="CLEAN",
            confidence=0.95,
            evidence={
                "structural": structural,
                "statistical": statistical,
                "semantic": semantic,
            },
            reason="clean_no_evidence",
            triggered_layer="none",
        )
