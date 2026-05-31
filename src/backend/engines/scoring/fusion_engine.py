"""Fusion Engine - Policy-only Decision Layer.

This module implements the final decision layer using the new architecture:
1. Feature Extractors (separate engines)
2. Evidence Aggregator (consolidates to 4 dimensions)
3. Rule Engine (policy-only, no scoring)
4. Verdict

Output format:
    VERDICT: CLEAN | REVIEW | PROBABLE | TRUE
    CONFIDENCE: rule-based (not fused score)
    EVIDENCE: per-dimension signals
    REASON: triggered rule
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

from src.backend.evaluation.arbitration import PrecisionWeightedFuser
from src.backend.engines.scoring.assignment_modes import assignment_modes_payload
from src.backend.engines.scoring.fusion_policy import (
    default_normalization_config,
    default_weight_governance_policy,
    fusion_presets_payload,
)
from src.backend.engines.scoring.evidence_ranker import EvidenceFusionRanker
from src.backend.engines.evidence_aggregator import (
    aggregate,
    aggregate_from_scores,
    EvidenceVector,
)
from src.backend.engines.decision_policy import DecisionPolicy, Decision

if TYPE_CHECKING:
    from src.backend.engines.features.feature_extractor import FeatureVector


@dataclass
class FusedScore:
    """Result of policy-only decision making."""

    final_score: float  # Rule-based confidence
    confidence: float = 0.8
    uncertainty: float = 0.0
    agreement_index: float = 1.0
    components: Dict[str, float] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)
    review_priority: float = 0.0
    professor_summary: str = ""
    evidence_reasons: list[str] = field(default_factory=list)
    evidence_guardrails: list[str] = field(default_factory=list)
    evidence_quality: Dict[str, str] = field(default_factory=dict)
    relevant_engines: List[str] = field(default_factory=list)
    verdict: str = "INCONCLUSIVE"


# Baseline scores expected for two unrelated files in the same language.
LANGUAGE_BASELINE: Dict[str, float] = {
    "embedding": 0.70,
    "winnowing": 0.25,
    "string_tiling": 0.20,
    "ngram": 0.15,
    "ast": 0.25,
    "graph": 0.20,
    "static_rules": 0.20,
    "fingerprint": 0.15,
    "sklearn_cosine": 0.25,
}

WEIGHT_ALIASES: Dict[str, str] = {
    "token": "fingerprint",
    "semantic": "embedding",
    "codebert": "embedding",
    "gst": "string_tiling",
    "cfg": "graph",
    "execution_cfg": "graph",
    "llm": "embedding",
}


CONFIG_PATH = Path(__file__).parent.parent / "engine_weights.yaml"


def load_engine_config() -> Dict:
    """Load engine configuration from YAML config file."""
    if not CONFIG_PATH.exists():
        return _get_default_config()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return _with_policy_defaults(config or {})
    except Exception:
        return _get_default_config()


def save_engine_config(config: Dict) -> None:
    """Save engine configuration to YAML config file with validation."""
    config = _with_policy_defaults(config)

    if "weights" in config:
        total = sum(config["weights"].values())
        if total > 0 and abs(total - 1.0) > 0.001:
            config["weights"] = {
                k: round(v / total, 4) for k, v in config["weights"].items()
            }

    for section in ["weights", "baseline_correction"]:
        if section in config:
            for key, value in config[section].items():
                if isinstance(value, (int, float)):
                    config[section][key] = max(0.0, min(1.0, value))

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)


def _get_default_config() -> Dict:
    return _with_policy_defaults(
        {
            "weights": {
                "token": 0.12,
                "winnowing": 0.16,
                "gst": 0.13,
                "ast": 0.17,
                "ngram": 0.10,
                "graph": 0.15,
                "embedding": 0.12,
                "static_rules": 0.05,
                "codebert": 0.00,
                "sklearn_cosine": 0.00,
            },
            "baseline_correction": {
                "enabled": True,
                "baselines": {
                    "embedding": 0.70,
                    "winnowing": 0.25,
                    "string_tiling": 0.20,
                    "ngram": 0.15,
                    "ast": 0.25,
                    "graph": 0.20,
                    "static_rules": 0.20,
                    "fingerprint": 0.15,
                    "sklearn_cosine": 0.25,
                },
            },
            "arbitration": {
                "enabled": True,
                "prior_precision_multiplier": 20.0,
                "minimum_agreement": 0.30,
            },
            "ast_boost": {
                "enabled": True,
                "threshold": 0.90,
                "minimum_guaranteed_score": 0.75,
            },
        }
    )


def _with_policy_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure fusion policy sections are present in loaded configuration."""
    config.setdefault("score_normalization", default_normalization_config())
    config.setdefault("fusion_presets", fusion_presets_payload())
    config.setdefault("weight_governance", default_weight_governance_policy())
    config.setdefault("assignment_modes", assignment_modes_payload())
    config.setdefault("advanced", {"hot_reload": True})
    return config


DEFAULT_WEIGHTS: Dict[str, float] = _get_default_config()["weights"]
LANGUAGE_BASELINE: Dict[str, float] = _get_default_config()["baseline_correction"][
    "baselines"
]


def hard_gate(
    evidence: Dict[str, float],
    coverage: float = 0.0,
) -> Optional[str]:
    """
    Hard gating layer to veto false positives.

    Rules:
    1. If max signal < 0.50: CLEAN (insufficient evidence)
    2. If no structural signals above 0.50: CLEAN
    3. If weak signals dominate: CLEAN
    4. If high similarity but low coverage: CLEAN (few matching lines)
    5. If low coverage with low identical_line_ratio: CLEAN

    Args:
        evidence: Dictionary of engine names to scores
        coverage: Fraction of code covered by matching segments (0.0-1.0).
                  Computed by CodeHighlighter based on line-level matches.

    Returns:
        "CLEAN" if vetoed, None if should proceed
    """
    if not evidence:
        return "CLEAN"

    max_signal = max(evidence.values())

    # Rule 1: Completely clean - no signal strong enough
    if max_signal < 0.50:
        return "CLEAN"

    # Rule 2: No structural evidence
    structural_signals = [
        "ast",
        "logic_flow",
        "ngram",
        "winnowing",
        "token",
        "fingerprint",
    ]
    structural_max = max(evidence.get(s, 0.0) for s in structural_signals)

    if structural_max < 0.50:
        return "CLEAN"

    # Rule 3: Coverage gate — if coverage is too low, veto
    # A high similarity score on a tiny matched region is a false positive signal
    if coverage < 0.15:
        return "CLEAN"

    # Rule 4: Disproportionate signal-to-coverage ratio
    # If max_signal is high (>0.80) but coverage is still modest (<0.40),
    # the high score comes from small isolated matches, not widespread copying
    if max_signal >= 0.80 and coverage < 0.40:
        return "CLEAN"

    return None


class FusionEngine:
    """Policy-only fusion engine with evidence aggregation."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self._config = load_engine_config()
        self._last_load_time = time.time()

        if weights is None:
            weights = self._config["weights"]

        self.weights: Dict[str, float] = self._normalize_weight_names(weights)
        self.baselines: Dict[str, float] = self._normalize_weight_names(
            self._config.get("baseline_correction", {}).get("baselines", {})
        )
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

        multiplier = self._config["arbitration"]["prior_precision_multiplier"]
        self._fuser = PrecisionWeightedFuser(
            engine_prior_precisions={k: v * multiplier for k, v in self.weights.items()}
        )
        self._ranker = EvidenceFusionRanker()

    @staticmethod
    def _normalize_weight_names(weights: Dict[str, float]) -> Dict[str, float]:
        """Map config-facing weight names to FeatureVector engine names."""
        normalized: Dict[str, float] = {}
        for name, value in weights.items():
            feature_name = WEIGHT_ALIASES.get(name, name)
            normalized[feature_name] = normalized.get(feature_name, 0.0) + float(value)
        return normalized

    def reload_config(self) -> None:
        """Reload configuration from disk if modified."""
        if self._config.get("advanced", {}).get("hot_reload", True):
            mtime = os.path.getmtime(CONFIG_PATH)
            if mtime > self._last_load_time:
                self.__init__()

    @classmethod
    def get_current_config(cls) -> Dict:
        """Get full current engine configuration."""
        return load_engine_config()

    @classmethod
    def update_config(cls, config: Dict) -> None:
        """Update and save engine configuration (Admin only)."""
        save_engine_config(config)

    @classmethod
    def get_standard_presets(cls) -> Dict[str, Dict[str, Any]]:
        """Get standard faculty presets."""
        return {
            "standard": {
                "name": "Standard (Recommended)",
                "description": "Production optimized default profile. Best overall accuracy.",
                "multipliers": {},
            },
            "conservative": {
                "name": "Conservative",
                "description": "Minimize false positives. For high-stakes assessments.",
                "multipliers": {
                    "token": 1.5,
                    "ngram": 1.5,
                    "winnowing": 1.5,
                    "ast": 0.9,
                    "graph": 1.2,
                    "execution": 0.7,
                    "embedding": 0.6,
                    "llm": 0.4,
                },
            },
        }

    @classmethod
    def get_assignment_presets(cls) -> Dict[str, Dict[str, Any]]:
        """Get assignment-aware presets with weights and evidence policy."""
        return fusion_presets_payload()

    @classmethod
    def run_calibration_benchmark(cls) -> Dict[str, Any]:
        """Run standard benchmark dataset and return accuracy metrics."""
        try:
            from src.backend.benchmark.datasets.ir_plag import IRPlagDataset
            from src.backend.evaluation.metrics import calculate_accuracy_metrics

            dataset = IRPlagDataset()
            results = []

            for pair in dataset.test_pairs:
                score = cls().fuse(pair.features)
                results.append(
                    {"score": score.final_score, "ground_truth": pair.is_plagiarized}
                )

            metrics = calculate_accuracy_metrics(results)
            return {
                "status": "completed",
                "f1": metrics.f1,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "accuracy": metrics.accuracy,
                "auc_roc": metrics.auc_roc,
                "roc_curve": metrics.roc_points,
                "optimal_threshold": metrics.optimal_threshold,
                "confusion_matrix": metrics.confusion_matrix,
                "total_pairs": len(results),
                "runtime_ms": metrics.runtime_ms,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def fuse(
        self,
        features: "FeatureVector",
        weight_multipliers: Optional[Dict[str, float]] = None,
        logic_flow: float = 0.0,
    ) -> FusedScore:
        """Make deterministic decision using policy rules.

        This method uses the DecisionPolicy for verdict decisions.
        NO score fusion or averaging is performed for the final decision.

        Args:
            features: A FeatureVector containing scores from each engine.
            weight_multipliers: Optional per-engine multipliers (deprecated).
            logic_flow: Optional pre-computed logic flow similarity score.

        Returns:
            A FusedScore with verdict, confidence, and evidence breakdown.
        """
        raw_scores = features.as_dict()
        raw_scores["logic_flow"] = logic_flow

        # Extract coverage from FeatureVector (computed by CodeHighlighter)
        coverage = getattr(features, "coverage", 0.0)

        # HARD GATE LAYER: Veto false positives before any processing
        veto = hard_gate(raw_scores, coverage=coverage)
        if veto == "CLEAN":
            return FusedScore(
                final_score=0.0,
                confidence=0.95,
                uncertainty=0.0,
                agreement_index=0.95,
                components=raw_scores,
                contributions={},
                review_priority=0.0,
                professor_summary="Hard gate veto: Insufficient evidence for plagiarism.",
                evidence_reasons=["No structural evidence", "Low signal strength"],
                evidence_guardrails=["max_signal < 0.50 or no structural evidence"],
                evidence_quality=self._calculate_evidence_quality(raw_scores, {}),
                relevant_engines=list(raw_scores.keys()),
                verdict="CLEAN",
            )

        # Check for exact match first - return 100% for identical files
        token_score = raw_scores.get("fingerprint", raw_scores.get("token", 0.0))
        if token_score >= 0.95:
            return FusedScore(
                final_score=1.0,
                confidence=0.99,
                uncertainty=0.0,
                agreement_index=0.99,
                components=raw_scores,
                contributions={},
                review_priority=1.0,
                professor_summary="Exact match detected - files are identical.",
                evidence_reasons=["Exact token sequence match"],
                evidence_guardrails=[],
                evidence_quality={"fingerprint": "conclusive"},
                relevant_engines=["fingerprint"],
                verdict="TRUE",
            )

        # FILE-TYPE DEPENDENT WEIGHTING
        # Apply weights based on file type classification
        file_type = getattr(features, "file_type", None)
        file_type_domain = getattr(features, "file_type_domain", None)

        from src.backend.engines.file_type_weights import (
            apply_weights,
            should_veto_embedding,
            FileType,
        )

        # Apply file-type dependent weights to raw scores
        weighted_scores = apply_weights(raw_scores, file_type)

        # Check if embedding should be vetoed for this file type
        if should_veto_embedding(file_type, file_type_domain):
            weighted_scores["embedding"] = 0.0

        # AGGREGATE: Consolidate to evidence vector (NO scoring)
        # Use weighted scores for evidence aggregation
        evidence = aggregate_from_scores(weighted_scores, logic_flow, coverage=coverage)

        # Apply baseline correction for display purposes only
        corrected_scores = {}
        for name, score in weighted_scores.items():
            baseline = self.baselines.get(name, LANGUAGE_BASELINE.get(name, 0.0))
            corrected = max(0.0, score - baseline) / max(0.01, 1.0 - baseline)
            corrected_scores[name] = round(corrected, 4)

        relevant_scores = {k: v for k, v in corrected_scores.items() if v > 0.0}

        # DECIDE: Policy-only decision (NO averaging)
        decision = DecisionPolicy.decide(evidence)

        # FILE-TYPE ADJUSTMENT: Downgrade high similarity for CONFIG files
        # driven by embedding or key overlap
        if file_type == FileType.CONFIG:
            embedding_weight = weighted_scores.get("embedding", 0)
            # If embedding was the main signal, downgrade the result
            max_signal = max(weighted_scores.values()) if weighted_scores else 0
            if embedding_weight > 0.7 * max_signal:
                # Embedding was dominant for CONFIG - downgrade
                new_confidence = min(decision.confidence, 0.4)
                new_verdict = (
                    "REVIEW"
                    if decision.verdict in ("TRUE", "PROBABLE")
                    else decision.verdict
                )
                decision = Decision(
                    verdict=new_verdict,
                    confidence=new_confidence,
                    evidence=decision.evidence,
                    reason="Config similarity driven by embedding/key overlap - downgraded",
                    triggered_layer=decision.triggered_layer,
                )

        # TSX/JSX ADJUSTMENT: Separate component-tree from boilerplate similarity
        # This prevents React pages with similar boilerplate from producing false positives
        tsx_result = None
        if file_type == FileType.CODE and features.file_type_domain in (
            "react",
            "next",
            "vue",
            "nuxt",
        ):
            from src.backend.engines.tsx_analyzer import analyze_tsx_similarity

            tsx_result = analyze_tsx_similarity(
                features._raw_code_a if hasattr(features, "_raw_code_a") else "",
                features._raw_code_b if hasattr(features, "_raw_code_b") else "",
            )
            if (
                tsx_result.get("has_jsx")
                and tsx_result.get("boilerplate_similarity", 0) > 0.5
            ):
                # Heavy boilerplate - apply discount
                discount = tsx_result.get("discount_factor", 1.0)
                new_confidence = decision.confidence * discount
                if new_confidence < decision.confidence:
                    decision = Decision(
                        verdict=decision.verdict,
                        confidence=new_confidence,
                        evidence=decision.evidence,
                        reason=f"TSX boilerplate discount applied ({discount:.0%})",
                        triggered_layer=decision.triggered_layer,
                    )

        return FusedScore(
            final_score=decision.confidence,
            confidence=decision.confidence,
            uncertainty=1.0 - decision.confidence,
            agreement_index=decision.confidence,
            components=raw_scores,
            contributions={},
            review_priority=1.0 if decision.verdict == "TRUE" else 0.0,
            professor_summary=f"Policy Decision: {decision.verdict}",
            evidence_reasons=[decision.reason],
            evidence_guardrails=[],
            evidence_quality=self._calculate_evidence_quality(
                raw_scores, relevant_scores
            ),
            relevant_engines=list(relevant_scores.keys()),
            verdict=decision.verdict,
        )

    def get_weights(self) -> Dict[str, float]:
        """Return the current normalized engine weights."""
        return dict(self.weights)

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Update and re-normalize engine weights."""
        self.weights = self._normalize_weight_names(weights)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        multiplier = self._config["arbitration"]["prior_precision_multiplier"]
        self._fuser = PrecisionWeightedFuser(
            engine_prior_precisions={k: v * multiplier for k, v in self.weights.items()}
        )

    @staticmethod
    def _calculate_evidence_quality(
        raw_scores: Dict[str, float], corrected_scores: Dict[str, float]
    ) -> Dict[str, str]:
        """Rate evidence quality for each engine."""
        quality = {}
        for name, score in raw_scores.items():
            if score <= 0.0:
                quality[name] = "none"
            elif score < 0.3:
                quality[name] = "weak"
            elif score < 0.6:
                quality[name] = "moderate"
            elif score < 0.85:
                quality[name] = "strong"
            else:
                quality[name] = "conclusive"
        return quality
