"""Fusion Engine - Evidence Hierarchy Engine integration.

This module now delegates to the Evidence Hierarchy Engine (EHE) for
hierarchical decision making that eliminates score pollution and
ensures deterministic verdicts.

Key improvements:
1. Identity evidence hard-stops the pipeline
2. Structural evidence dominates semantic evidence
3. No weighted averaging across evidence types
4. Full audit trail in every decision
5. Hard gating layer to veto false positives
6. Conflict-based downgrade to REVIEW
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
from src.backend.engines.detection.ehe import EvidenceHierarchyEngine, Verdict as EHEVerdict

if TYPE_CHECKING:
    from src.backend.engines.features.feature_extractor import FeatureVector


@dataclass
class FusedScore:
    """Result of fused multi-engine similarity scoring."""

    final_score: float
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
            config["weights"] = {k: round(v / total, 4) for k, v in config["weights"].items()}

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
    return config


DEFAULT_WEIGHTS: Dict[str, float] = _get_default_config()["weights"]
LANGUAGE_BASELINE: Dict[str, float] = _get_default_config()["baseline_correction"][
    "baselines"
]


def hard_gate(evidence: Dict[str, float]) -> Optional[str]:
    """
    Hard gating layer to veto false positives.
    
    This is the FIRST check before any scoring. It prevents weak signals
    from accumulating into false plagiarism accusations.
    
    Rules:
    1. If max signal < 0.50: CLEAN (insufficient evidence)
    2. If no structural signals (ast, logic_flow, ngram, winnowing) above 0.50: CLEAN
    3. If weak signals dominate (all signals < 0.5): CLEAN
    
    Args:
        evidence: Dictionary of engine names to scores
        
    Returns:
        "CLEAN" if vetoed, None if should proceed to EHE
    """
    if not evidence:
        return "CLEAN"
    
    max_signal = max(evidence.values())
    
    # Rule 1: Completely clean - no signal strong enough to warrant review
    if max_signal < 0.50:
        return "CLEAN"
    
    # Rule 2: No structural evidence - semantic similarity alone is not plagiarism
    # Check multiple structural signal keys
    ast_score = evidence.get("ast", 0.0)
    flow_score = evidence.get("logic_flow", 0.0)
    ngram_score = evidence.get("ngram", 0.0)
    winnowing_score = evidence.get("winnowing", 0.0)
    token_score = evidence.get("token", 0.0)
    fingerprint_score = evidence.get("fingerprint", 0.0)
    
    # Any structural signal above 0.5
    structural_max = max(ast_score, flow_score, ngram_score, winnowing_score, token_score, fingerprint_score)
    
    if structural_max < 0.50:
        return "CLEAN"
    
    # Rule 3: Weak signal accumulation veto
    # Multiple weak signals should NOT be treated as strong evidence
    weak_signals = [v for v in evidence.values() if v < 0.5]
    strong_signals = [v for v in evidence.values() if v >= 0.5]
    
    # If majority of signals are weak and no strong signals exist
    if len(weak_signals) > len(strong_signals) and len(strong_signals) == 0:
        return "CLEAN"
    
    return None  # Proceed to EHE


def check_conflict(evidence: Dict[str, float]) -> bool:
    """
    Check if evidence shows high variance/conflict indicating unreliable signals.
    
    High variance in evidence suggests the signals are inconsistent and
    should be treated as unreliable rather than indicative of plagiarism.
    
    Args:
        evidence: Dictionary of engine names to scores
        
    Returns:
        True if evidence is conflicted (should downgrade to REVIEW)
    """
    if len(evidence) < 3:
        return False
    
    values = list(evidence.values())
    mean_val = sum(values) / len(values)
    
    # Calculate variance
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    
    # High variance threshold (signals are inconsistent)
    return variance > 0.05


class FusionEngine:
    """Multi-engine fusion scoring authority with EHE integration.

    This engine now uses the Evidence Hierarchy Engine (EHE) for
    hierarchical decision making that:
    - Eliminates score pollution (100% → 82%)
    - Establishes evidence priority (Identity > Structural > Statistical > Semantic)
    - Guarantees consistent, explainable, auditable decisions
    - Hard gates false positives before processing
    - Downgrades conflicted evidence to REVIEW
    """

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
        self._ehe = EvidenceHierarchyEngine()

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
        if self._config["advanced"].get("hot_reload", True):
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
    ) -> FusedScore:
        """Combine engine outputs using Evidence Hierarchy Engine.

        This method delegates to EHE for hierarchical decision making.

        Args:
            features: A FeatureVector containing scores from each engine.
            weight_multipliers: Optional per-engine multipliers (deprecated).

        Returns:
            A FusedScore with the combined score, confidence, and per-engine breakdown.
        """
        raw_scores = features.as_dict()

        # HARD GATE LAYER: Veto false positives before any processing
        veto = hard_gate(raw_scores)
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
                evidence_guardrails=["max_signal < 0.60 or no structural evidence"],
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

        # Apply baseline correction
        corrected_scores = {}
        for name, score in raw_scores.items():
            baseline = self.baselines.get(name, LANGUAGE_BASELINE.get(name, 0.0))
            corrected = max(0.0, score - baseline) / max(0.01, 1.0 - baseline)
            corrected_scores[name] = round(corrected, 4)

        relevant_scores = {k: v for k, v in corrected_scores.items() if v > 0.0}

        # CONFLICT CHECK: Downgrade if evidence is inconsistent
        conflicted = check_conflict(raw_scores)

        # Use EHE for decision (hierarchical, not weighted)
        ehe_decision = self._ehe.decide(code_a="", code_b="", engine_scores=raw_scores)

        verdict_map = {
            EHEVerdict.TRUE: "TRUE",
            EHEVerdict.PROBABLE: "PROBABLE",
            EHEVerdict.REVIEW: "REVIEW",
            EHEVerdict.CLEAN: "CLEAN",
        }

        evidence_quality = self._calculate_evidence_quality(raw_scores, relevant_scores)

        # Ensure confidence is a valid number
        confidence = ehe_decision.confidence
        if confidence is None or not isinstance(confidence, (int, float)) or confidence != confidence:  # NaN check
            confidence = 0.5
        
        # CONFLICT DOWNGRADE: If evidence conflicted, downgrade to REVIEW
        if conflicted and ehe_decision.verdict != EHEVerdict.CLEAN:
            final_verdict = "REVIEW"
            confidence = min(confidence, 0.5)  # Cap confidence for conflicted evidence
        else:
            final_verdict = verdict_map.get(ehe_decision.verdict, "INCONCLUSIVE")

        return FusedScore(
            final_score=confidence,
            confidence=confidence,
            uncertainty=1.0 - confidence,
            agreement_index=confidence,
            components=raw_scores,
            contributions={},
            review_priority=1.0 if ehe_decision.verdict == EHEVerdict.TRUE else 0.0,
            professor_summary=f"EHE Decision: {ehe_decision.verdict}",
            evidence_reasons=ehe_decision.decision_path,
            evidence_guardrails=[] if not conflicted else ["Evidence conflict detected"],
            evidence_quality=evidence_quality,
            relevant_engines=list(relevant_scores.keys()),
            verdict=final_verdict,
        )

    def run_three_layer_pipeline(
        self,
        code_a: str,
        code_b: str,
        engine_scores: Dict[str, float],
        engine_details: Optional[Dict[str, Any]] = None,
        domain: str = "code",
    ) -> Dict[str, Any]:
        """Run the three-layer detection pipeline using EHE."""
        from src.backend.engines.detection.layer1_deterministic import Layer1Deterministic
        from src.backend.engines.detection.layer2_statistical import Layer2Statistical
        from src.backend.engines.detection.layer3_semantic import Layer3Semantic
        from src.backend.engines.detection.layer4_explainability import Layer4Explainability
        from src.backend.engines.detection.detection_policy import DetectionPolicy

        l1 = Layer1Deterministic()
        l2 = Layer2Statistical()
        l3 = Layer3Semantic()
        l4 = Layer4Explainability()
        policy = DetectionPolicy(domain=domain)

        l1_result = l1.evaluate(code_a, code_b, engine_scores, engine_details)
        l2_result = l2.evaluate(code_a, code_b, engine_scores, engine_details)
        l3_result = l3.evaluate(code_a, code_b, engine_scores, engine_details)
        l4_result = l4.evaluate(code_a, code_b, engine_scores, engine_details)

        report = policy.evaluate(
            l1_result, l2_result, l3_result,
            course_type=domain,
            explanation_report=l4_result,
        )

        # Use EHE confidence as the score (rule-based, not averaged)
        report.additive_score = report.layer1_value  # Use strongest layer value

        return report.to_legacy_dict()

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