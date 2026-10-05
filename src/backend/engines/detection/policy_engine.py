"""Policy Engine - declarative rule-based decision system.

Evaluates the rules in ``policy.yaml`` to produce deterministic, auditable verdicts.

Principles:
1. Rules are evaluated in priority order (first match wins).
2. Evidence types are NOT averaged: each rule checks specific conditions.
3. Output is fully auditable: decision path, evaluated rules, policy hash.

What was wrong before (each changed verdicts silently):
- A condition with several keys (``{a: ">= 0.5", b: ">= 0.5"}``) evaluated only the FIRST key
  and returned; now every key must hold.
- ``"<= 0.5"`` was parsed by the ``startswith("<")`` branch first and raised ``ValueError``.
- The YAML fallback rule ``if: {true: ...}`` parsed to the key ``True`` and never matched; the
  "fallback" verdict only existed because of a hard-coded last resort. ``if: true`` works now.
- A missing evidence value was 0.0, so ``embedding: "< 0.30"`` held whenever the embedding engine
  was unavailable and the "evidence contradiction" rule fired. Missing is now UNKNOWN: every
  comparison with it is false.
- The ``embedding`` the rules saw was the RAW cosine similarity (about 0.70 for unrelated files), so
  ``embedding >= 0.75`` was nearly noise. It is the baseline-corrected value now (raw under
  ``embedding_raw``).
- Evidence keys the caller passed could overwrite ``flat_evidence`` / ``layer_values``.
- The dotted aliases (``layer1.has_exact_file_match``) were never resolved.
- A broken policy file silently became a 3-rule policy. The engine still falls back, but marks
  every audit record ``degraded``; an invalid rule invalidates the whole file instead of being
  half-applied; the audit record carries the SHA-256 of the policy that decided.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ._text import score

logger = logging.getLogger(__name__)

POLICY_CONFIG_PATH = Path(__file__).parent / "policy.yaml"

VALID_VERDICTS = frozenset({"TRUE", "PROBABLE", "REVIEW", "FLAG", "CLEAN"})
_OPERATION = re.compile(r"^\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
_ALWAYS_KEYS = {True, "true", "always"}  # YAML turns a bare ``true:`` key into the boolean True
_COMBINATORS = {"and", "or", "not", "if"}
_ALIASES = {
    "exact_match": "layer1.has_exact_file_match",
    "structural": "layer_values.layer2",
    "lexical": "layer_values.layer1",
    "semantic": "layer_values.layer3",
}


class PolicyError(ValueError):
    """The policy file is invalid."""


def _compare(operator: str, left: float, right: float) -> bool:
    return {
        ">=": left >= right,
        "<=": left <= right,
        ">": left > right,
        "<": left < right,
        "==": left == right,
        "!=": left != right,
    }[operator]


def validate_condition(condition: Any, where: str = "condition") -> None:
    """Raise :class:`PolicyError` for a condition the engine could not evaluate."""
    if isinstance(condition, bool):
        return
    if not isinstance(condition, dict) or not condition:
        raise PolicyError(f"{where}: a condition must be true/false or a non-empty mapping, got {condition!r}")
    for key, value in condition.items():
        if key in _ALWAYS_KEYS:
            continue
        if key in ("and", "or"):
            if not isinstance(value, list) or not value:
                raise PolicyError(f"{where}.{key}: must be a non-empty list")
            for index, item in enumerate(value):
                validate_condition(item, f"{where}.{key}[{index}]")
        elif key in ("not", "if"):
            validate_condition(value, f"{where}.{key}")
        elif isinstance(value, bool) or isinstance(value, (int, float)):
            continue
        elif isinstance(value, str):
            if not _OPERATION.match(value):
                raise PolicyError(f"{where}.{key}: {value!r} is not '<op> <number>' with op in >= <= > < == !=")
        else:
            raise PolicyError(f"{where}.{key}: unsupported value {value!r}")


@dataclass
class PolicyRule:
    """A single policy rule with condition and action."""

    id: str
    priority: int
    condition: dict[str, Any] | bool
    verdict: str
    confidence: float
    reason: str

    def matches(self, evidence: dict[str, Any]) -> bool:
        """Whether this rule's condition holds for the evidence."""
        return self._evaluate_condition(self.condition, evidence)

    def _evaluate_condition(self, condition: Any, evidence: dict[str, Any]) -> bool:
        """Recursively evaluate a condition (every key of a mapping must hold)."""
        if isinstance(condition, bool):
            return condition
        if not isinstance(condition, dict) or not condition:
            return False

        results: list[bool] = []
        for key, value in condition.items():
            if key in _ALWAYS_KEYS:
                results.append(True if value is None else bool(value))
            elif key == "if":
                results.append(self._evaluate_condition(value, evidence))
            elif key == "and":
                results.append(all(self._evaluate_condition(c, evidence) for c in value))
            elif key == "or":
                results.append(any(self._evaluate_condition(c, evidence) for c in value))
            elif key == "not":
                results.append(not self._evaluate_condition(value, evidence))
            else:
                results.append(self._check(key, value, evidence))
        return all(results)

    def _check(self, key: str, expected: Any, evidence: dict[str, Any]) -> bool:
        actual = self._get_evidence_value(key, evidence)
        if isinstance(expected, bool):
            return bool(actual) == expected  # missing counts as False for flags such as exact_match
        if actual is None:
            return False  # unknown evidence satisfies no numeric comparison
        if isinstance(expected, (int, float)):
            return actual == float(expected)
        match = _OPERATION.match(expected)
        return bool(match) and _compare(match.group(1), actual, float(match.group(2)))

    def _get_evidence_value(self, key: str, evidence: dict[str, Any], _depth: int = 0) -> float | None:
        """Evidence value for ``key`` (None when missing/unusable). Dotted paths and aliases work."""
        for source in (evidence.get("flat_evidence", {}), evidence.get("layer_values", {})):
            if isinstance(source, dict) and key in source:
                return self._as_float(source[key])
        if "." in key:
            node: Any = evidence
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    node = None
                    break
                node = node[part]
            if node is not None:
                return self._as_float(node)
        elif key in evidence and not isinstance(evidence[key], (dict, list)):
            return self._as_float(evidence[key])
        if key in _ALIASES and _depth < 3:
            return self._get_evidence_value(_ALIASES[key], evidence, _depth + 1)
        return None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""

    verdict: str
    confidence: float
    reason: str
    decision_path: list[str] = field(default_factory=list)
    matched_rule: str | None = None
    raw_evidence: dict[str, Any] = field(default_factory=dict)
    rules_evaluated: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "decision_path": self.decision_path,
            "matched_rule": self.matched_rule,
            "rules_evaluated": self.rules_evaluated,
        }


def _default_policy() -> dict[str, Any]:
    return {
        "version": "1.0-default",
        "rules": {
            "identity_override": {
                "if": {"exact_match": True},
                "then": {"verdict": "TRUE", "confidence": 0.99, "reason": "Exact match detected", "priority": 1},
            },
            "structural_dominance": {
                "if": {"logic_flow": ">= 0.95"},
                "then": {"verdict": "TRUE", "confidence": 0.95, "reason": "Strong structural equivalence", "priority": 2},
            },
            "fallback": {
                "if": True,
                "then": {"verdict": "CLEAN", "confidence": 0.10, "reason": "No significant similarity", "priority": 99},
            },
        },
    }


class PolicyEngine:
    """Evaluates the declarative rules; the first matching rule (by priority) wins."""

    def __init__(self, policy_path: Path | None = None):
        """
        Args:
            policy_path: Path to ``policy.yaml`` (the packaged one when None).
        """
        self.policy_path = Path(policy_path) if policy_path else POLICY_CONFIG_PATH
        self.degraded = False
        self.degraded_reason = ""
        self.source = "file"
        self.config = self._load_policy()
        self.rules = self._parse_rules()
        self.version = str(self.config.get("version", "1.0"))
        self.policy_hash = hashlib.sha256(
            json.dumps(self.config, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    # ------------------------------------------------------------------ loading

    def _fall_back(self, reason: str) -> dict[str, Any]:
        logger.error("Policy %s unusable (%s); using the built-in default policy", self.policy_path, reason)
        self.degraded, self.degraded_reason, self.source = True, reason, "default"
        return _default_policy()

    def _load_policy(self) -> dict[str, Any]:
        """Load and validate the policy; any problem selects the (marked) default policy."""
        if not self.policy_path.exists():
            return self._fall_back("file not found")
        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if not isinstance(config, dict) or not isinstance(config.get("rules"), dict) or not config["rules"]:
                raise PolicyError("the policy needs a non-empty 'rules' mapping")
            self._validate(config)
            return config
        except Exception as exc:  # noqa: BLE001
            return self._fall_back(str(exc))

    @staticmethod
    def _validate(config: dict[str, Any]) -> None:
        for rule_id, rule in config["rules"].items():
            if not isinstance(rule, dict) or "if" not in rule or not isinstance(rule.get("then"), dict):
                raise PolicyError(f"rule {rule_id!r} needs 'if' and 'then'")
            then = rule["then"]
            if str(then.get("verdict", "")).upper() not in VALID_VERDICTS:
                raise PolicyError(f"rule {rule_id!r}: verdict {then.get('verdict')!r} is not one of {sorted(VALID_VERDICTS)}")
            confidence = then.get("confidence", 0.5)
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
                raise PolicyError(f"rule {rule_id!r}: confidence must be in [0, 1]")
            if not isinstance(then.get("priority", 999), int):
                raise PolicyError(f"rule {rule_id!r}: priority must be an integer")
            validate_condition(rule["if"], f"rule {rule_id!r}")

    def _parse_rules(self) -> list[PolicyRule]:
        rules = []
        for rule_id, rule_config in self.config.get("rules", {}).items():
            then = rule_config.get("then", {})
            rules.append(
                PolicyRule(
                    id=str(rule_id),
                    priority=int(then.get("priority", 999)),
                    condition=rule_config.get("if", {}),
                    verdict=str(then.get("verdict", "CLEAN")).upper(),
                    confidence=float(then.get("confidence", 0.5)),
                    reason=str(then.get("reason", "Rule matched")),
                )
            )
        return sorted(rules, key=lambda r: r.priority)  # stable: equal priorities keep file order

    # ------------------------------------------------------------------ evaluation

    @staticmethod
    def build_flat_evidence(layer1_value: float, layer2_value: float, evidence: dict[str, Any]) -> dict[str, Any]:
        """Evidence by name; engines that did not report are ABSENT (unknown), not 0.0."""
        l1 = evidence.get("layer1") or {}
        l2 = evidence.get("layer2") or {}
        l3 = evidence.get("layer3") or {}
        s1, s2, s3 = (l1.get("engine_scores") or {}), (l2.get("engine_scores") or {}), (l3.get("engine_scores") or {})
        flat: dict[str, Any] = {"exact_match": bool(l1.get("has_exact_file_match", False))}
        for name, source, key in (
            ("ast", s1, "ast"),
            ("token_overlap", s1, "token"),
            ("winnowing", s1, "winnowing"),
            ("ngram", s1, "ngram"),
            ("logic_flow", s2, "logic_flow"),
            ("graph", s2, "graph"),
            ("embedding_raw", s3, "embedding"),
        ):
            value = source.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                flat[name] = float(value)
        # rules see the baseline-corrected embedding (raw ~0.70 for any two files of a language)
        corrected = s3.get("embedding_corrected")
        if isinstance(corrected, (int, float)) and math.isfinite(corrected):
            flat["embedding"] = float(corrected)
        flat["structural"] = layer2_value
        flat["lexical"] = layer1_value
        return flat

    def evaluate(
        self,
        layer1_value: float,
        layer2_value: float,
        layer3_value: float,
        evidence: dict[str, Any],
        audit_info: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate the evidence against the rules.

        Args:
            layer1_value, layer2_value, layer3_value: layer scores in [0, 1] (NaN/None count as 0).
            evidence: per-layer evidence dicts (``layer1`` / ``layer2`` / ``layer3`` ``to_dict()`` output).
            audit_info: optional audit metadata (stored by :meth:`get_audit_record`).
        """
        l1, l2, l3 = score(layer1_value), score(layer2_value), score(layer3_value)
        evidence = evidence if isinstance(evidence, dict) else {}
        evaluation_evidence = {
            **evidence,  # first: the engine's own entries below cannot be overwritten by the caller
            "layer_values": {"layer1": l1, "layer2": l2, "layer3": l3},
            "flat_evidence": self.build_flat_evidence(l1, l2, evidence),
        }

        evaluated: list[str] = []
        for rule in self.rules:
            evaluated.append(rule.id)
            if rule.matches(evaluation_evidence):
                return PolicyDecision(
                    verdict=rule.verdict,
                    confidence=rule.confidence,
                    reason=rule.reason,
                    decision_path=[rule.id],
                    matched_rule=rule.id,
                    raw_evidence=evaluation_evidence,
                    rules_evaluated=evaluated,
                )

        # No rule matched and the policy has no fallback: say so (the policy should end with one).
        return PolicyDecision(
            verdict="CLEAN",
            confidence=0.10,
            reason="No rule matched (implicit fallback)",
            decision_path=["implicit_fallback"],
            matched_rule="implicit_fallback",
            raw_evidence=evaluation_evidence,
            rules_evaluated=evaluated,
        )

    def rule_thresholds(self) -> dict[str, float]:
        """Every numeric threshold in the policy as ``{"rule.key": value}`` (for audit display)."""
        found: dict[str, float] = {}

        def walk(rule_id: str, node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in _COMBINATORS or key in _ALWAYS_KEYS:
                        walk(rule_id, value)
                    elif isinstance(value, str) and (m := _OPERATION.match(value)):
                        label, n = f"{rule_id}.{key}{m.group(1)}", 2
                        while label in found:
                            label, n = f"{rule_id}.{key}{m.group(1)}#{n}", n + 1
                        found[label] = float(m.group(2))
            elif isinstance(node, list):
                for item in node:
                    walk(rule_id, item)

        for rule in self.rules:
            walk(rule.id, rule.condition)
        return found

    def get_audit_record(self, decision: PolicyDecision, audit_info: dict[str, Any] | None = None) -> dict[str, Any]:
        """Complete audit record, including WHICH policy decided."""
        return {
            "policy_version": self.version,
            "policy_hash": self.policy_hash,
            "policy_source": self.source,
            "policy_degraded": self.degraded,
            "policy_degraded_reason": self.degraded_reason,
            "verdict": decision.verdict,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "decision_path": decision.decision_path,
            "matched_rule": decision.matched_rule,
            "rules_evaluated": decision.rules_evaluated,
            "evidence_snapshot": decision.raw_evidence,
            "audit_metadata": audit_info or {},
        }
