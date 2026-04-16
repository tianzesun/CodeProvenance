"""
Pass/fail validation rules for benchmark results.

Formal acceptance criteria and validation rules that define whether
a tool's performance meets minimum acceptable standards for the benchmark.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from ..evaluation.metrics import calculate_precision_recall_f1
from ..evaluation.statistics import confidence_interval


class ValidationRuleType(Enum):
    """Type of validation rule."""
    ABSOLUTE_THRESHOLD = "absolute_threshold"
    BASELINE_COMPARISON = "baseline_comparison"
    CONFIDENCE_INTERVAL = "confidence_interval"
    MINIMUM_SAMPLE_SIZE = "minimum_sample_size"


@dataclass
class ValidationRule:
    """
    A single validation rule that must be satisfied for a tool to pass.
    """
    rule_id: str
    rule_type: ValidationRuleType
    metric: str
    threshold: float
    baseline: str = None
    confidence_level: float = 0.95
    description: str = ""

    def evaluate(self, tool_result: Dict[str, Any], baseline_results: Dict[str, Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate this rule against tool results.

        Returns:
            Tuple of (passed: bool, details: dict)
        """
        if self.metric not in tool_result:
            return False, {
                "passed": False,
                "error": f"Metric {self.metric} not found in result",
                "rule_id": self.rule_id
            }

        value = tool_result[self.metric]

        if self.rule_type == ValidationRuleType.ABSOLUTE_THRESHOLD:
            passed = value >= self.threshold
            return passed, {
                "passed": passed,
                "rule_id": self.rule_id,
                "value": value,
                "threshold": self.threshold,
                "metric": self.metric,
                "description": self.description
            }

        if self.rule_type == ValidationRuleType.BASELINE_COMPARISON:
            if not baseline_results or self.baseline not in baseline_results:
                return False, {
                    "passed": False,
                    "error": f"Baseline {self.baseline} not available for comparison",
                    "rule_id": self.rule_id
                }
            baseline_value = baseline_results[self.baseline][self.metric]
            passed = value >= baseline_value * self.threshold
            return passed, {
                "passed": passed,
                "rule_id": self.rule_id,
                "value": value,
                "baseline_value": baseline_value,
                "relative_performance": value / baseline_value if baseline_value > 0 else 0,
                "threshold_ratio": self.threshold,
                "metric": self.metric,
                "baseline_tool": self.baseline,
                "description": self.description
            }

        return False, {"passed": False, "error": "Unsupported rule type", "rule_id": self.rule_id}


class BenchmarkPassFailValidator:
    """
    Validator that applies all configured validation rules to produce
    an overall pass/fail outcome for a candidate tool.
    """

    def __init__(self, rules: List[ValidationRule]):
        self.rules = rules

    def validate(self, tool_result: Dict[str, Any], baseline_results: Dict[str, Dict[str, Any]] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Run all validation rules against the tool result.

        Returns:
            Tuple of (overall_passed: bool, rule_results: list)
        """
        rule_results = []
        all_passed = True

        for rule in self.rules:
            passed, details = rule.evaluate(tool_result, baseline_results)
            if not passed:
                all_passed = False
            rule_results.append(details)

        return all_passed, rule_results


# Standard baseline validation rules
STANDARD_VALIDATION_RULES = [
    ValidationRule(
        rule_id="min_precision",
        rule_type=ValidationRuleType.ABSOLUTE_THRESHOLD,
        metric="precision",
        threshold=0.7,
        description="Minimum precision of 0.7 required"
    ),
    ValidationRule(
        rule_id="min_recall",
        rule_type=ValidationRuleType.ABSOLUTE_THRESHOLD,
        metric="recall",
        threshold=0.6,
        description="Minimum recall of 0.6 required"
    ),
    ValidationRule(
        rule_id="min_f1",
        rule_type=ValidationRuleType.ABSOLUTE_THRESHOLD,
        metric="f1",
        threshold=0.65,
        description="Minimum F1 score of 0.65 required"
    ),
    ValidationRule(
        rule_id="moss_comparison",
        rule_type=ValidationRuleType.BASELINE_COMPARISON,
        metric="f1",
        threshold=0.85,
        baseline="moss",
        description="Must achieve at least 85% of MOSS F1 score"
    )
]
