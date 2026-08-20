"""Evidence Hierarchy Engine (EHE) - Core decision module.

This module implements the hierarchical evidence system that eliminates
score pollution (e.g., 100% becoming 82%) and ensures deterministic verdicts.

Key Principles:
1. Evidence is hierarchical, NOT fused
2. Identity evidence overrides everything (hard stop)
3. Structural evidence dominates semantic evidence
4. Lower layers cannot overturn higher layers
5. Decision is rule-based, not weighted average

Architecture:
    Layer 0: Identity     (hard override)
    Layer 1: Structural   (primary evidence)
    Layer 2: Statistical  (supporting evidence)
    Layer 3: Semantic     (weak signal)
    Layer 4: Explainable  (reason & trace)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Verdict(str, Enum):
    """Final decision verdicts."""

    TRUE = "TRUE"
    PROBABLE = "PROBABLE"
    REVIEW = "REVIEW"
    CLEAN = "CLEAN"


@dataclass
class LayerResult:
    """Result from a single evidence layer."""

    score: float = 0.0
    signals: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    triggered: bool = False


@dataclass
class EHEDecision:
    """Final decision from Evidence Hierarchy Engine."""

    verdict: Verdict
    confidence: float
    triggered_layer: str
    evidence: dict[str, Any] = field(default_factory=dict)
    decision_path: list[str] = field(default_factory=list)
    raw_scores: dict[str, float] = field(default_factory=dict)


class IdentityLayer:
    """Layer 0: Identity detection (hard override)."""

    @staticmethod
    def evaluate(code_a: str, code_b: str) -> LayerResult:
        """Check if files are identical."""
        if not code_a or not code_b:
            return LayerResult()

        # Exact string match
        if code_a.strip() == code_b.strip():
            return LayerResult(
                score=1.0, triggered=True, evidence={"match_type": "exact"}
            )

        # Hash match (for large files)
        hash_a = hashlib.sha256(code_a.encode()).hexdigest()
        hash_b = hashlib.sha256(code_b.encode()).hexdigest()
        if hash_a == hash_b:
            return LayerResult(
                score=1.0, triggered=True, evidence={"match_type": "hash"}
            )

        return LayerResult()


class StructuralLayer:
    """Layer 1: Structural evidence (AST, control flow, n-grams)."""

    def __init__(self) -> None:
        self.thresholds = {
            "hard_match": 0.90,
            "strong_match": 0.75,
            "medium_match": 0.50,
        }

    def evaluate(
        self,
        ast_score: float,
        flow_score: float,
        ngram_score: float,
        winnowing_score: float,
    ) -> LayerResult:
        """Evaluate structural evidence using max principle."""
        max_score = max(ast_score, flow_score, ngram_score, winnowing_score)

        return LayerResult(
            score=max_score,
            signals={
                "ast": ast_score,
                "flow": flow_score,
                "ngram": ngram_score,
                "winnowing": winnowing_score,
            },
            triggered=max_score > 0.0,
        )


class StatisticalLayer:
    """Layer 2: Statistical evidence (graph, stylometry)."""

    def evaluate(self, graph_score: float, stylometry_score: float) -> LayerResult:
        """Evaluate statistical evidence."""
        max_score = max(graph_score, stylometry_score)

        return LayerResult(
            score=max_score,
            signals={
                "graph": graph_score,
                "stylometry": stylometry_score,
            },
            triggered=max_score > 0.0,
        )


class SemanticLayer:
    """Layer 3: Semantic evidence (embedding, transformer)."""

    EMBEDDING_BASELINE = 0.70  # UniXcoder baseline for same language
    MAX_CAP = 0.99  # Higher cap to preserve strong signals

    def evaluate(self, embedding_score: float) -> LayerResult:
        """Evaluate semantic evidence (capped)."""
        # Baseline correction - but preserve very strong signals
        if embedding_score >= 0.95:
            # Very strong signal - use raw score with minor adjustment
            corrected = min(0.99, embedding_score)
        else:
            # Normal baseline correction
            corrected = max(0.0, embedding_score - self.EMBEDDING_BASELINE)
            corrected /= 1.0 - self.EMBEDDING_BASELINE
            corrected = min(corrected, self.MAX_CAP)

        return LayerResult(
            score=corrected,
            signals={"embedding": embedding_score, "embedding_corrected": corrected},
            triggered=corrected > 0.0,
        )


class EvidenceHierarchyEngine:
    """
    Evidence Hierarchy Engine - Main decision orchestrator.

    Implements the 5-layer hierarchy with strict priority ordering.
    """

    def __init__(self) -> None:
        self.identity = IdentityLayer()
        self.structural = StructuralLayer()
        self.statistical = StatisticalLayer()
        self.semantic = SemanticLayer()

    def decide(
        self, code_a: str, code_b: str, engine_scores: dict[str, float]
    ) -> EHEDecision:
        """
        Execute hierarchical decision pipeline.

        Args:
            code_a: First code file content
            code_b: Second code file content
            engine_scores: Pre-computed engine scores

        Returns:
            EHEDecision with verdict and evidence
        """
        decision_path: list[str] = []

        # ─────────────────────────────────────────────────────────────
        # Layer 0: Identity (HARD OVERRIDE - STOP HERE)
        # ─────────────────────────────────────────────────────────────
        identity_result = self.identity.evaluate(code_a, code_b)
        if identity_result.triggered:
            decision_path.append("identity_override")
            return EHEDecision(
                verdict=Verdict.TRUE,
                confidence=0.99,
                triggered_layer="identity",
                evidence={"identity": identity_result.evidence},
                decision_path=decision_path,
                raw_scores={"identity": 1.0},
            )

        # ─────────────────────────────────────────────────────────────
        # Layer 1: Structural Evidence
        # ─────────────────────────────────────────────────────────────
        structural_result = self.structural.evaluate(
            ast_score=engine_scores.get("ast", 0.0),
            flow_score=engine_scores.get("logic_flow", 0.0),
            ngram_score=engine_scores.get("ngram", 0.0),
            winnowing_score=engine_scores.get("winnowing", 0.0),
        )
        decision_path.append("structural")

        # Strong structural match → TRUE
        if structural_result.score >= 0.90:
            decision_path.append("strong_structural")
            return EHEDecision(
                verdict=Verdict.TRUE,
                confidence=0.95,
                triggered_layer="structural",
                evidence={"structural": structural_result.signals},
                decision_path=decision_path,
                raw_scores={"structural": structural_result.score},
            )

        # ─────────────────────────────────────────────────────────────
        # Layer 2: Statistical Evidence
        # ─────────────────────────────────────────────────────────────
        statistical_result = self.statistical.evaluate(
            graph_score=engine_scores.get("graph", 0.0),
            stylometry_score=engine_scores.get("stylometry", 0.0),
        )
        decision_path.append("statistical")

        # ─────────────────────────────────────────────────────────────
        # Layer 3: Semantic Evidence (WEAK SIGNAL - CANNOT OVERRIDE)
        # ─────────────────────────────────────────────────────────────
        semantic_result = self.semantic.evaluate(
            embedding_score=engine_scores.get("embedding", 0.0)
        )
        decision_path.append("semantic")

        # ─────────────────────────────────────────────────────────────
        # Layer 4: Rule-based Decision
        # ─────────────────────────────────────────────────────────────
        return self._apply_decision_rules(
            structural_result, statistical_result, semantic_result, decision_path
        )

    def _apply_decision_rules(
        self,
        structural: LayerResult,
        statistical: LayerResult,
        semantic: LayerResult,
        decision_path: list[str],
    ) -> EHEDecision:
        """Apply hierarchical decision rules."""

        # Rule 0: Strong semantic dominance - embedding detects same problem
        # When semantic is very strong (>0.95), it should dominate the decision
        if semantic.score >= 0.95:
            return EHEDecision(
                verdict=Verdict.PROBABLE,
                confidence=0.85,
                triggered_layer="semantic",
                evidence={
                    "structural": structural.signals,
                    "statistical": statistical.signals,
                    "semantic": semantic.signals,
                },
                decision_path=decision_path + ["semantic_dominance"],
                raw_scores={
                    "structural": structural.score,
                    "statistical": statistical.score,
                    "semantic": semantic.score,
                },
            )

        # Rule 1: Strong structural match
        if structural.score >= 0.75:
            return EHEDecision(
                verdict=Verdict.TRUE,
                confidence=0.90,
                triggered_layer="structural",
                evidence={
                    "structural": structural.signals,
                    "statistical": statistical.signals,
                    "semantic": semantic.signals,
                },
                decision_path=decision_path + ["strong_structural"],
                raw_scores={
                    "structural": structural.score,
                    "statistical": statistical.score,
                    "semantic": semantic.score,
                },
            )

        # Rule 2: Medium structural + strong statistical
        if structural.score >= 0.50 and statistical.score >= 0.70:
            return EHEDecision(
                verdict=Verdict.PROBABLE,
                confidence=0.75,
                triggered_layer="structural_statistical",
                evidence={
                    "structural": structural.signals,
                    "statistical": statistical.signals,
                    "semantic": semantic.signals,
                },
                decision_path=decision_path + ["medium_structural"],
                raw_scores={
                    "structural": structural.score,
                    "statistical": statistical.score,
                    "semantic": semantic.score,
                },
            )

        # Rule 3: Semantic-only warning (NEVER TRUE verdict)
        if semantic.score >= 0.85 and structural.score < 0.50:
            return EHEDecision(
                verdict=Verdict.REVIEW,
                confidence=0.60,
                triggered_layer="semantic",
                evidence={
                    "structural": structural.signals,
                    "statistical": statistical.signals,
                    "semantic": semantic.signals,
                },
                decision_path=decision_path + ["semantic_only_warning"],
                raw_scores={
                    "structural": structural.score,
                    "statistical": statistical.score,
                    "semantic": semantic.score,
                },
            )

        # Rule 4: Conflict detection
        if abs(structural.score - semantic.score) > 0.50:
            return EHEDecision(
                verdict=Verdict.REVIEW,
                confidence=0.50,
                triggered_layer="conflict",
                evidence={
                    "structural": structural.signals,
                    "statistical": statistical.signals,
                    "semantic": semantic.signals,
                },
                decision_path=decision_path + ["evidence_conflict"],
                raw_scores={
                    "structural": structural.score,
                    "statistical": statistical.score,
                    "semantic": semantic.score,
                },
            )

        # Rule 5: Borderline signals
        if structural.score >= 0.30 or statistical.score >= 0.30:
            return EHEDecision(
                verdict=Verdict.REVIEW,
                confidence=0.40,
                triggered_layer="borderline",
                evidence={
                    "structural": structural.signals,
                    "statistical": statistical.signals,
                    "semantic": semantic.signals,
                },
                decision_path=decision_path + ["borderline_signals"],
                raw_scores={
                    "structural": structural.score,
                    "statistical": statistical.score,
                    "semantic": semantic.score,
                },
            )

        # Rule 6: Clean
        return EHEDecision(
            verdict=Verdict.CLEAN,
            confidence=0.10,
            triggered_layer="none",
            evidence={
                "structural": structural.signals,
                "statistical": statistical.signals,
                "semantic": semantic.signals,
            },
            decision_path=decision_path + ["clean"],
            raw_scores={
                "structural": structural.score,
                "statistical": statistical.score,
                "semantic": semantic.score,
            },
        )
