"""Policy Engine - Declarative rule-based decision system.

This module implements a Policy-as-Code engine that evaluates declarative
rules from policy.yaml to produce deterministic plagiarism verdicts.

Key Design Principles:
1. Rules are evaluated in priority order (first match wins)
2. Evidence types are NOT averaged - each rule checks specific conditions
3. Output is fully auditable with decision path tracing
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)

POLICY_CONFIG_PATH = Path(__file__).parent / "policy.yaml"


@dataclass
class PolicyRule:
    """A single policy rule with condition and action."""

    id: str
    priority: int
    condition: Dict[str, Any]
    verdict: str
    confidence: float
    reason: str

    def matches(self, evidence: Dict[str, Any]) -> bool:
        """Check if this rule's condition matches the evidence."""
        return self._evaluate_condition(self.condition, evidence)

    def _evaluate_condition(self, condition: Any, evidence: Dict[str, Any]) -> bool:
        """Recursively evaluate a condition against evidence."""
        if isinstance(condition, bool):
            return condition

        if isinstance(condition, dict):
            if "if" in condition:
                return self._evaluate_condition(condition["if"], evidence)

            if "and" in condition:
                return all(
                    self._evaluate_condition(c, evidence) for c in condition["and"]
                )

            if "or" in condition:
                return any(
                    self._evaluate_condition(c, evidence) for c in condition["or"]
                )

            # Key-value condition: check if evidence matches threshold
            for key, value in condition.items():
                evidence_value = self._get_evidence_value(key, evidence)

                if isinstance(value, str) and value.startswith(">="):
                    threshold = float(value[2:])
                    return evidence_value >= threshold
                elif isinstance(value, str) and value.startswith("<"):
                    threshold = float(value[1:])
                    return evidence_value < threshold
                elif isinstance(value, str) and value.startswith(">"):
                    threshold = float(value[1:])
                    return evidence_value > threshold
                elif isinstance(value, str) and value.startswith("<="):
                    threshold = float(value[2:])
                    return evidence_value <= threshold
                elif isinstance(value, bool):
                    return evidence_value == value
                elif isinstance(value, (int, float)):
                    return evidence_value == value

        return False

    def _get_evidence_value(self, key: str, evidence: Dict[str, Any]) -> float:
        """Get evidence value for a key, with fallbacks for aliases."""
        # Direct lookup
        if key in evidence:
            return float(evidence[key])

        # Check layer values
        layer_values = evidence.get("layer_values", {})
        if key in layer_values:
            return float(layer_values[key])

        # Check flattened evidence
        flat_evidence = evidence.get("flat_evidence", {})
        if key in flat_evidence:
            return float(flat_evidence[key])

        # Aliases for common evidence types
        aliases = {
            "exact_match": "layer1.has_exact_file_match",
            "structural": "layer2.graph_similarity",
            "lexical": "layer1.token_overlap",
        }

        if key in aliases:
            return self._get_evidence_value(aliases[key], evidence)

        return 0.0


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""

    verdict: str
    confidence: float
    reason: str
    decision_path: List[str] = field(default_factory=list)
    matched_rule: Optional[str] = None
    raw_evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "decision_path": self.decision_path,
            "matched_rule": self.matched_rule,
        }


class PolicyEngine:
    """
    Policy Engine that evaluates declarative rules.

    Loads rules from policy.yaml and evaluates them in priority order.
    First matching rule wins.
    """

    def __init__(self, policy_path: Optional[Path] = None):
        """
        Initialize PolicyEngine with optional custom policy path.

        Args:
            policy_path: Path to policy.yaml. Uses default if None.
        """
        self.policy_path = policy_path or POLICY_CONFIG_PATH
        self.config = self._load_policy()
        self.rules = self._parse_rules()
        self.version = self.config.get("version", "1.0")

    def _load_policy(self) -> Dict[str, Any]:
        """Load policy configuration from YAML file."""
        if not self.policy_path.exists():
            logger.warning(f"Policy file not found: {self.policy_path}, using defaults")
            return self._default_policy()

        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load policy: {e}")
            return self._default_policy()

    def _default_policy(self) -> Dict[str, Any]:
        """Return default policy configuration."""
        return {
            "version": "1.0",
            "decision_order": ["identity_override", "structural_dominance", "fallback"],
            "rules": {
                "identity_override": {
                    "if": {"exact_match": True},
                    "then": {
                        "verdict": "TRUE",
                        "confidence": 0.99,
                        "reason": "Exact match detected",
                        "priority": 1,
                    },
                },
                "structural_dominance": {
                    "if": {"logic_flow": ">= 0.95"},
                    "then": {
                        "verdict": "TRUE",
                        "confidence": 0.95,
                        "reason": "Strong structural equivalence",
                        "priority": 2,
                    },
                },
                "fallback": {
                    "if": True,
                    "then": {
                        "verdict": "CLEAN",
                        "confidence": 0.10,
                        "reason": "No significant similarity",
                        "priority": 99,
                    },
                },
            },
        }

    def _parse_rules(self) -> List[PolicyRule]:
        """Parse rules from configuration."""
        rules = []
        raw_rules = self.config.get("rules", {})

        for rule_id, rule_config in raw_rules.items():
            then = rule_config.get("then", {})
            rule = PolicyRule(
                id=rule_id,
                priority=then.get("priority", 999),
                condition=rule_config.get("if", {}),
                verdict=then.get("verdict", "CLEAN"),
                confidence=then.get("confidence", 0.5),
                reason=then.get("reason", "Rule matched"),
            )
            rules.append(rule)

        # Sort by priority
        return sorted(rules, key=lambda r: r.priority)

    def evaluate(
        self,
        layer1_value: float,
        layer2_value: float,
        layer3_value: float,
        evidence: Dict[str, Any],
        audit_info: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """
        Evaluate evidence against policy rules.

        Args:
            layer1_value: Deterministic layer score
            layer2_value: Statistical layer score
            layer3_value: Semantic layer score
            evidence: Detailed evidence breakdown
            audit_info: Optional audit metadata

        Returns:
            PolicyDecision with verdict and audit trail
        """
        # Build flat evidence structure for rule evaluation
        flat_evidence = {
            "exact_match": evidence.get("layer1", {}).get(
                "has_exact_file_match", False
            ),
            "ast": evidence.get("layer1", {}).get("engine_scores", {}).get("ast", 0.0),
            "token_overlap": evidence.get("layer1", {})
            .get("engine_scores", {})
            .get("token", 0.0),
            "winnowing": evidence.get("layer1", {})
            .get("engine_scores", {})
            .get("winnowing", 0.0),
            "ngram": evidence.get("layer1", {})
            .get("engine_scores", {})
            .get("ngram", 0.0),
            "logic_flow": evidence.get("layer2", {})
            .get("engine_scores", {})
            .get("logic_flow", 0.0),
            "graph": evidence.get("layer2", {})
            .get("engine_scores", {})
            .get("graph", 0.0),
            "embedding": evidence.get("layer3", {})
            .get("engine_scores", {})
            .get("embedding", 0.0),
            "structural": layer2_value,
            "lexical": layer1_value,
        }

        evaluation_evidence = {
            "layer_values": {
                "layer1": layer1_value,
                "layer2": layer2_value,
                "layer3": layer3_value,
            },
            "flat_evidence": flat_evidence,
            **evidence,
        }

        decision_path: List[str] = []

        for rule in self.rules:
            if rule.matches(evaluation_evidence):
                decision_path.append(rule.id)

                return PolicyDecision(
                    verdict=rule.verdict,
                    confidence=rule.confidence,
                    reason=rule.reason,
                    decision_path=decision_path,
                    matched_rule=rule.id,
                    raw_evidence=evaluation_evidence,
                )

        # Should never reach here due to fallback rule
        return PolicyDecision(
            verdict="CLEAN",
            confidence=0.10,
            reason="No rule matched (fallback)",
            decision_path=["fallback"],
            matched_rule="fallback",
            raw_evidence=evaluation_evidence,
        )

    def get_audit_record(
        self, decision: PolicyDecision, audit_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete audit record for the decision.

        Args:
            decision: The policy decision
            audit_info: Metadata about who/when triggered analysis

        Returns:
            Complete audit record dictionary
        """
        return {
            "policy_version": self.version,
            "verdict": decision.verdict,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "decision_path": decision.decision_path,
            "matched_rule": decision.matched_rule,
            "evidence_snapshot": decision.raw_evidence,
            "audit_metadata": audit_info or {},
        }
