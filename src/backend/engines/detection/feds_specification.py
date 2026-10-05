"""
Formal Evidence Decision Specification (FEDS) - Policy-Based Version

This module provides a deterministic, auditable, and defensible
decision system for plagiarism detection using the Policy Engine.

Decision Hierarchy:
    1. Identity Override Rules (exact match detection)
    2. Structural Dominance Rules (high structural similarity)
    3. Mixed Evidence Rules (combined signals)
    4. Conflict Resolution Rules (contradictory evidence)
    5. Low-Confidence Fallback Rules (inconclusive cases)

Verdict Scale:
    TRUE       → Definite plagiarism — actionable evidence chain
    PROBABLE   → Likely plagiarism — needs manual review
    REVIEW     → Borderline — human inspection required
    FLAG       → Semantic-only signal — review required, high FP risk
    CLEAN      → No evidence of plagiarism

Anti-Patterns Explicitly Forbidden:
    - Weighted averaging across unrelated evidence types
    - Embedding overriding structural evidence
    - Single-score final decision systems
    - Black-box probability fusion without explanation
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.backend.engines.detection._text import score as _unit
from src.backend.engines.detection.policy_engine import PolicyEngine


@dataclass
class EvidenceModel:
    """
    Formal evidence model defining how each evidence type should be represented.

    Each evidence type has:
    - semantic_meaning: Human-understandable description
    - valid_range: (min, max) valid score range
    - reliability_constraints: Conditions for reliable detection
    """

    semantic_meaning: str
    valid_range: tuple[float, float]
    reliability_constraints: list[str]

    @classmethod
    def get_models(cls) -> dict[str, EvidenceModel]:
        """Return evidence models for all evidence types."""
        return {
            "identity": cls(
                semantic_meaning="Exact or near-identical file matches",
                valid_range=(0.0, 1.0),
                reliability_constraints=[
                    "Token sequence match ≥ 0.95 indicates identical files",
                    "Reliable only when fingerprint score ≥ 0.95",
                ],
            ),
            "structural": cls(
                semantic_meaning="Code structure and organization similarity",
                valid_range=(0.0, 1.0),
                reliability_constraints=[
                    "AST similarity ≥ 0.70 indicates significant structural overlap",
                    "CFG similarity ≥ 0.60 indicates control flow similarity",
                ],
            ),
            "lexical": cls(
                semantic_meaning="Token-level and n-gram sequence similarity",
                valid_range=(0.0, 1.0),
                reliability_constraints=[
                    "Winnowing hash collision rate < 0.01",
                    "N-gram overlap must exceed language baseline",
                ],
            ),
            "semantic": cls(
                semantic_meaning="Meaning-level code similarity",
                valid_range=(0.0, 0.90),
                reliability_constraints=[
                    "NEVER standalone verdict source",
                    "Requires L1 or L2 corroboration",
                    "Baseline-corrected, then capped at 0.90 to prevent false positives",
                ],
            ),
            "behavioral": cls(
                semantic_meaning="Writing style and pattern similarity",
                valid_range=(0.0, 1.0),
                reliability_constraints=[
                    "Stylometric distance < 0.3 indicates similar authors",
                    "Requires multiple behavioral signals for reliability",
                ],
            ),
        }


@dataclass
class FEDSDecision:
    """
    Output of the FEDS decision process.

    All fields are auditable and can be traced back to specific evidence.
    """

    verdict: str  # TRUE, PROBABLE, REVIEW, FLAG, CLEAN
    confidence: float  # Calibrated confidence score (0.0-1.0)
    reason: str  # Human-readable reason
    decision_path: list[str]  # Exact rules triggered
    evidence_summary: dict[str, Any]  # Structured evidence breakdown
    layer_values: dict[str, float]  # L1, L2, L3 values
    thresholds_used: dict[str, float]  # Actual thresholds applied
    audit_record: dict[str, Any] = field(default_factory=dict)  # Full audit trail

    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible form (the audit record's evidence snapshot is included as is)."""
        return asdict(self)


class FEDS:
    """
    Formal Evidence Decision Specification using Policy Engine.

    Delegates decision logic to declarative rules in policy.yaml.
    Ensures consistent, auditable, and defensible verdicts.
    """

    def __init__(self, policy_engine: PolicyEngine | None = None):
        """
        Initialize FEDS with optional custom PolicyEngine.

        Args:
            policy_engine: Custom policy engine. Creates default if None.
        """
        self.policy_engine = policy_engine or PolicyEngine()

    def evaluate(
        self,
        layer1_value: float,
        layer2_value: float,
        layer3_value: float,
        evidence: dict[str, Any],
        audit_info: dict[str, Any] | None = None,
    ) -> FEDSDecision:
        """
        Evaluate evidence and produce a deterministic verdict.

        Args:
            layer1_value: Deterministic layer score (0.0-1.0; NaN/None count as 0)
            layer2_value: Statistical layer score (0.0-1.0)
            layer3_value: Semantic layer score (0.0-0.95)
            evidence: Detailed evidence breakdown by layer
            audit_info: Optional audit metadata (who, when, why)

        Returns:
            FEDSDecision with verdict and audit trail
        """
        layer1_value, layer2_value, layer3_value = (
            _unit(layer1_value),
            _unit(layer2_value),
            _unit(layer3_value),
        )
        # Get policy decision
        policy_decision = self.policy_engine.evaluate(
            layer1_value, layer2_value, layer3_value, evidence, audit_info
        )

        # Get audit record
        audit_record = self.policy_engine.get_audit_record(policy_decision, audit_info)

        return FEDSDecision(
            verdict=policy_decision.verdict,
            confidence=policy_decision.confidence,
            reason=policy_decision.reason,
            decision_path=policy_decision.decision_path,
            evidence_summary=evidence,
            layer_values={
                "layer1": round(layer1_value, 4),
                "layer2": round(layer2_value, 4),
                "layer3": round(layer3_value, 4),
            },
            thresholds_used=self.policy_engine.rule_thresholds(),  # every numeric threshold in policy.yaml
            audit_record=audit_record,
        )


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE DECISION CASES
# ═══════════════════════════════════════════════════════════════════════════
# The examples used to carry only layer values. Most rules key on ENGINE evidence (exact_match,
# logic_flow, ...), so with those inputs the engine returned CLEAN for every case and the
# documented "expected" verdicts were fiction. Each case now includes the evidence that triggers
# its rule, and run_example_cases() checks them against the real engine.
EXAMPLE_CASES = [
    {
        "name": "Identical Files",
        "description": "Two files with exact same content",
        "input": {"l1": 1.0, "l2": 0.95, "l3": 0.90},
        "evidence": {
            "layer1": {"has_exact_file_match": True, "engine_scores": {"ast": 1.0}}
        },
        "expected_verdict": "TRUE",
        "rule_triggered": "identity_override",
        "explanation": "The files are identical. No semantic analysis needed.",
    },
    {
        "name": "Heavily Plagiarized",
        "description": "Files with near-identical control/logic flow",
        "input": {"l1": 0.88, "l2": 0.97, "l3": 0.85},
        "evidence": {"layer2": {"engine_scores": {"logic_flow": 0.97}}},
        "expected_verdict": "TRUE",
        "rule_triggered": "structural_dominance",
        "explanation": "Strong structural equivalence detected.",
    },
    {
        "name": "Semantic-Only Similarity",
        "description": "Files with high semantic similarity but different structure",
        "input": {"l1": 0.30, "l2": 0.25, "l3": 0.92},
        "evidence": {
            "layer3": {
                "engine_scores": {"embedding": 0.99, "embedding_corrected": 0.92}
            }
        },
        # Semantic evidence is declared "NEVER standalone verdict source", and the
        # policy enforces it: a high embedding score with no structural match
        # corroborates nothing and must not raise a verdict on its own. This case
        # used to expect FLAG, which contradicted that constraint.
        "expected_verdict": "CLEAN",
        "rule_triggered": "no_structural_support",
        "explanation": (
            "High embedding similarity alone is not evidence of copying - embedding "
            "models score unrelated files highly too. With no structural or lexical "
            "match to corroborate it, there is nothing to review."
        ),
    },
    {
        "name": "Borderline Case",
        "description": "Files with moderate signals across layers",
        "input": {"l1": 0.55, "l2": 0.45, "l3": 0.35},
        "evidence": {"layer1": {"engine_scores": {"token": 0.55}}},
        "expected_verdict": "REVIEW",
        "rule_triggered": "review_zone",
        "explanation": "Borderline signals - too weak for automated action, too strong to ignore.",
    },
    {
        "name": "Clean Files",
        "description": "Two unrelated files with no significant similarity",
        "input": {"l1": 0.10, "l2": 0.15, "l3": 0.20},
        "evidence": {},
        "expected_verdict": "CLEAN",
        "rule_triggered": "fallback",
        "explanation": "All layers below minimum thresholds - no evidence of plagiarism.",
    },
]


def run_example_cases(feds: FEDS | None = None) -> list[dict[str, Any]]:
    """Evaluate every example against the real policy and report whether it behaves as documented."""
    feds = feds or FEDS()
    report = []
    for case in EXAMPLE_CASES:
        decision = feds.evaluate(
            case["input"]["l1"],
            case["input"]["l2"],
            case["input"]["l3"],
            case["evidence"],
        )
        report.append(
            {
                "name": case["name"],
                "ok": decision.verdict == case["expected_verdict"]
                and decision.decision_path == [case["rule_triggered"]],
                "verdict": decision.verdict,
                "rule": decision.decision_path,
            }
        )
    return report
