"""Policy layer for multi-engine fusion.

This module keeps scale normalization, assignment presets, and weight-change
governance separate from the final fusion math. The separation matters because
external engines report scores on incompatible scales, and default-weight changes
must be auditable against benchmark validation results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_INTERNAL_ENGINE_IDS = {
    "ast",
    "fingerprint",
    "token",
    "winnowing",
    "ngram",
    "gst",
    "embedding",
    "semantic",
    "execution_cfg",
    "tree_kernel",
    "cfg",
    "web",
    "ai_detection",
}


@dataclass(frozen=True)
class ScoreNormalizationRule:
    """Normalize one engine's raw score to the common [0, 1] similarity scale."""

    method: str = "unit"
    minimum: float = 0.0
    maximum: float = 1.0
    higher_is_more_similar: bool = True

    def normalize(self, value: Any) -> float:
        """Return a clamped similarity score in the [0, 1] interval."""
        try:
            raw = float(value)
        except (TypeError, ValueError):
            raw = 0.0

        if self.method == "percent":
            scaled = raw / 100.0 if raw > 1.0 else raw
        elif self.method == "min_max":
            span = max(self.maximum - self.minimum, 1e-9)
            scaled = (raw - self.minimum) / span
        else:
            scaled = raw

        if not self.higher_is_more_similar:
            scaled = 1.0 - scaled

        return round(max(0.0, min(1.0, scaled)), 4)


@dataclass(frozen=True)
class ScoreNormalizer:
    """Normalize raw scores from internal and external engines before fusion."""

    rules: Dict[str, ScoreNormalizationRule] = field(default_factory=dict)
    default_rule: ScoreNormalizationRule = field(default_factory=ScoreNormalizationRule)

    def normalize(self, engine_id: str, value: Any) -> float:
        """Normalize one score for the named engine."""
        rule = self.rules.get(engine_id, self.default_rule)
        return rule.normalize(value)

    def normalize_many(self, scores: Dict[str, Any]) -> Dict[str, float]:
        """Normalize a mapping of engine IDs to raw score values."""
        return {
            engine_id: self.normalize(engine_id, score)
            for engine_id, score in scores.items()
        }


@dataclass(frozen=True)
class FusionPreset:
    """Assignment-specific fusion preset and evidence policy."""

    preset_id: str
    name: str
    description: str
    weights: Dict[str, float]
    evidence_surfaces: List[str]
    pipelines: List[str] = field(default_factory=lambda: ["code"])
    present_results_separately: bool = False

    def normalized_weights(self) -> Dict[str, float]:
        """Return preset weights normalized to sum to 1.0."""
        positive_weights = {
            key: max(0.0, float(value)) for key, value in self.weights.items()
        }
        total = sum(positive_weights.values())
        if total <= 0.0:
            return positive_weights
        return {key: round(value / total, 4) for key, value in positive_weights.items()}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the preset for API and config payloads."""
        return {
            "id": self.preset_id,
            "name": self.name,
            "description": self.description,
            "weights": self.normalized_weights(),
            "evidence_surfaces": list(self.evidence_surfaces),
            "pipelines": list(self.pipelines),
            "present_results_separately": self.present_results_separately,
        }


@dataclass(frozen=True)
class WeightGovernanceResult:
    """Result of checking whether a default weight change is ready to ship."""

    allowed: bool
    requires_validation: bool
    changed_engines: List[str]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the governance result for API responses."""
        return {
            "allowed": self.allowed,
            "requires_validation": self.requires_validation,
            "changed_engines": self.changed_engines,
            "warnings": self.warnings,
        }


def default_score_normalizer() -> ScoreNormalizer:
    """Build the default score normalizer for known engines and tools."""
    percent_rule = ScoreNormalizationRule(method="percent", minimum=0.0, maximum=100.0)
    unit_rule = ScoreNormalizationRule(method="unit", minimum=0.0, maximum=1.0)

    rules = {engine_id: unit_rule for engine_id in DEFAULT_INTERNAL_ENGINE_IDS}
    rules.update(
        {
            "moss": percent_rule,
            "jplag": percent_rule,
            "dolos": percent_rule,
            "nicad": percent_rule,
            "sherlock": percent_rule,
            "pmd": percent_rule,
        }
    )
    return ScoreNormalizer(rules=rules, default_rule=unit_rule)


def default_normalization_config() -> Dict[str, Any]:
    """Return a config-friendly description of default normalization rules."""
    return {
        "common_scale": "similarity_probability_0_to_1",
        "external_tools": {
            "moss": {"method": "percent", "range": [0, 100]},
            "jplag": {"method": "percent", "range": [0, 100]},
            "dolos": {"method": "percent", "range": [0, 100]},
            "nicad": {"method": "percent", "range": [0, 100]},
            "sherlock": {"method": "percent", "range": [0, 100]},
            "pmd": {"method": "percent", "range": [0, 100]},
        },
        "internal_engines": {"method": "unit", "range": [0, 1]},
        "calibration_note": (
            "Normalization only aligns score scales. Probability calibration still "
            "requires labeled train/validation data per engine."
        ),
    }


def get_fusion_presets() -> Dict[str, FusionPreset]:
    """Return assignment-type presets for code, text, and mixed submissions."""
    presets = [
        FusionPreset(
            preset_id="algorithm_data_structure",
            name="Algorithm/Data Structure",
            description=(
                "Emphasizes structural evidence for assignments with shared boilerplate "
                "and common textbook patterns."
            ),
            weights={
                "ast": 0.28,
                "tree_kernel": 0.20,
                "cfg": 0.16,
                "execution_cfg": 0.16,
                "token": 0.08,
                "winnowing": 0.06,
                "gst": 0.04,
                "semantic": 0.02,
            },
            evidence_surfaces=[
                "ast_structure",
                "control_flow",
                "execution_behavior",
                "token_overlap",
                "hard_negative_context",
            ],
        ),
        FusionPreset(
            preset_id="open_ended_coding",
            name="Open-ended Coding",
            description=(
                "Balances lexical, structural, and semantic evidence for projects "
                "where implementations can legitimately differ."
            ),
            weights={
                "ast": 0.22,
                "token": 0.14,
                "winnowing": 0.10,
                "gst": 0.10,
                "semantic": 0.20,
                "execution_cfg": 0.14,
                "tree_kernel": 0.06,
                "cfg": 0.04,
            },
            evidence_surfaces=[
                "semantic_similarity",
                "ast_structure",
                "token_overlap",
                "execution_behavior",
                "side_by_side_diff",
            ],
        ),
        FusionPreset(
            preset_id="essay_report",
            name="Essay/Report",
            description=(
                "Prioritizes text similarity and AI-writing evidence while suppressing "
                "code-only evidence surfaces."
            ),
            weights={
                "semantic": 0.34,
                "web": 0.22,
                "ai_detection": 0.28,
                "token": 0.10,
                "winnowing": 0.06,
            },
            evidence_surfaces=[
                "text_similarity",
                "source_overlap",
                "ai_detection",
                "citation_context",
                "false_positive_risk",
            ],
            pipelines=["text"],
        ),
        FusionPreset(
            preset_id="mixed_submission",
            name="Mixed Submission",
            description=(
                "Runs code and write-up pipelines independently and reports the evidence "
                "separately so one modality does not hide the other."
            ),
            weights={
                "ast": 0.18,
                "token": 0.10,
                "winnowing": 0.08,
                "gst": 0.07,
                "semantic": 0.20,
                "web": 0.12,
                "ai_detection": 0.12,
                "execution_cfg": 0.08,
                "tree_kernel": 0.03,
                "cfg": 0.02,
            },
            evidence_surfaces=[
                "code_similarity",
                "text_similarity",
                "ai_detection",
                "side_by_side_diff",
                "separate_pipeline_summary",
            ],
            pipelines=["code", "text"],
            present_results_separately=True,
        ),
    ]
    return {preset.preset_id: preset for preset in presets}


def fusion_presets_payload() -> Dict[str, Any]:
    """Return all fusion presets as a serializable payload."""
    return {
        preset_id: preset.to_dict()
        for preset_id, preset in get_fusion_presets().items()
    }


def default_weight_governance_policy() -> Dict[str, Any]:
    """Return the default governance rule for shipping preset/default weights."""
    return {
        "default_weight_changes_require_validation": True,
        "required_split": "validation",
        "locked_test_set_policy": "test split is used only for final published results",
        "required_evidence": [
            "validation_run_id",
            "benchmark_dataset_id",
            "metric_snapshot",
        ],
        "allowed_roles": ["admin", "developer"],
        "audit_log_required": True,
    }


def evaluate_weight_change_governance(
    current_weights: Dict[str, float],
    proposed_weights: Dict[str, float],
    evidence: Optional[Dict[str, Any]] = None,
) -> WeightGovernanceResult:
    """Check whether default engine-weight changes have validation evidence."""
    evidence = evidence or {}
    changed_engines = _changed_weight_keys(current_weights, proposed_weights)

    if not changed_engines:
        return WeightGovernanceResult(
            allowed=True,
            requires_validation=False,
            changed_engines=[],
            warnings=[],
        )

    warnings = []
    required_fields = ["validation_run_id", "benchmark_dataset_id", "metric_snapshot"]
    missing_fields = [field for field in required_fields if not evidence.get(field)]
    if missing_fields:
        warnings.append(
            "Default fusion weights changed without validation evidence: "
            + ", ".join(missing_fields)
        )

    split = str(evidence.get("split") or "")
    if split and split != "validation":
        warnings.append(
            "Default fusion weights must be tuned against the validation split, "
            f"not '{split}'."
        )
    elif not split:
        warnings.append("Default fusion weight changes must name the validation split.")

    if evidence.get("used_locked_test_set"):
        warnings.append(
            "Locked test-set results cannot be used for iterative weight tuning."
        )

    return WeightGovernanceResult(
        allowed=not warnings,
        requires_validation=True,
        changed_engines=changed_engines,
        warnings=warnings,
    )


def _changed_weight_keys(
    current_weights: Dict[str, float],
    proposed_weights: Dict[str, float],
    tolerance: float = 0.0001,
) -> List[str]:
    """Return sorted engine names whose proposed weights differ from current weights."""
    keys: Iterable[str] = set(current_weights) | set(proposed_weights)
    return sorted(
        key
        for key in keys
        if abs(
            float(current_weights.get(key, 0.0)) - float(proposed_weights.get(key, 0.0))
        )
        > tolerance
    )
