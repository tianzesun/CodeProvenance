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

import copy
import logging
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from src.backend.engines.decision_policy import Decision, DecisionPolicy
from src.backend.engines.evidence_aggregator import (
    aggregate_from_scores,
)
from src.backend.engines.scoring.assignment_modes import assignment_modes_payload
from src.backend.engines.scoring.evidence_ranker import EvidenceFusionRanker
from src.backend.engines.scoring.fusion_policy import (
    default_normalization_config,
    default_weight_governance_policy,
    fusion_presets_payload,
)
from src.backend.evaluation.arbitration import PrecisionWeightedFuser

if TYPE_CHECKING:
    from src.backend.engines.features.feature_extractor import FeatureVector

logger = logging.getLogger(__name__)

#: A shared (starter-code / boilerplate dominated) match is never auto-escalated past this.
STARTER_OVERLAP_CAP = 0.70


@dataclass
class FusedScore:
    """Result of policy-only decision making."""

    final_score: float  # Rule-based confidence
    confidence: float = 0.8
    uncertainty: float = 0.0
    agreement_index: float = 1.0
    components: dict[str, float] = field(default_factory=dict)
    contributions: dict[str, float] = field(default_factory=dict)
    review_priority: float = 0.0
    professor_summary: str = ""
    evidence_reasons: list[str] = field(default_factory=list)
    evidence_guardrails: list[str] = field(default_factory=list)
    evidence_quality: dict[str, str] = field(default_factory=dict)
    relevant_engines: list[str] = field(default_factory=list)
    verdict: str = "INCONCLUSIVE"


WEIGHT_ALIASES: dict[str, str] = {
    "token": "fingerprint",
    "semantic": "embedding",
    "codebert": "embedding",
    "gst": "string_tiling",
    "cfg": "graph",
    "execution_cfg": "graph",
    "llm": "embedding",
}


CONFIG_PATH = Path(__file__).parent.parent / "engine_weights.yaml"


_config_lock = threading.Lock()


def load_engine_config() -> dict:
    """Load engine configuration from YAML config file.

    Missing sections are filled from the defaults (a YAML without ``weights`` or
    ``arbitration`` used to crash ``FusionEngine.__init__`` with a KeyError), and a broken file
    is logged instead of silently replaced by the defaults.
    """
    if not CONFIG_PATH.exists():
        return _get_default_config()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if config is not None and not isinstance(config, dict):
            raise TypeError(f"engine config must be a mapping, got {type(config).__name__}")
        return _with_policy_defaults(config or {})
    except Exception as exc:
        logger.warning("Could not read %s (%s); using the default engine configuration", CONFIG_PATH, exc)
        return _get_default_config()


def _finite_non_negative(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0.0 else None


def save_engine_config(config: dict) -> None:
    """Save engine configuration to YAML config file with validation.

    The caller's dict is not modified; weights must be finite and non-negative (they were
    normalised BEFORE negatives were clamped, and NaN passed straight through); booleans such as
    ``baseline_correction.enabled`` are no longer turned into 1.0; and the file is replaced
    atomically so a crash or a concurrent reader never sees a half-written config.
    """
    config = _with_policy_defaults(copy.deepcopy(config))

    weights = config.get("weights")
    if isinstance(weights, dict):
        clean: dict[str, float] = {}
        for key, value in weights.items():
            number = _finite_non_negative(value)
            if number is None:
                raise ValueError(f"weight {key!r} must be a finite, non-negative number, got {value!r}")
            clean[key] = number
        total = sum(clean.values())
        if total > 0 and abs(total - 1.0) > 0.001:
            clean = {k: round(v / total, 4) for k, v in clean.items()}
        config["weights"] = {k: max(0.0, min(1.0, v)) for k, v in clean.items()}

    baselines = config.get("baseline_correction")
    if isinstance(baselines, dict):
        for key, value in list(baselines.items()):
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                baselines[key] = max(0.0, min(1.0, float(value))) if math.isfinite(value) else 0.0
        inner = baselines.get("baselines")
        if isinstance(inner, dict):
            for key, value in list(inner.items()):
                number = _finite_non_negative(value)
                inner[key] = max(0.0, min(1.0, number)) if number is not None else 0.0

    with _config_lock:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=CONFIG_PATH.parent, prefix=".engine_weights.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(config, handle, sort_keys=False, default_flow_style=False)
                handle.flush()
                os.fsync(handle.fileno())
            if CONFIG_PATH.exists():
                os.chmod(tmp_name, CONFIG_PATH.stat().st_mode & 0o777)
            os.replace(tmp_name, CONFIG_PATH)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def _base_config() -> dict:
    return {
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


def _get_default_config() -> dict:
    return _with_policy_defaults(_base_config())


def _fill_missing(target: dict, defaults: dict) -> None:
    """Recursively add keys that ``target`` lacks (never overwrites)."""
    for key, value in defaults.items():
        if key not in target or target[key] is None:
            target[key] = copy.deepcopy(value)
        elif key != "weights" and isinstance(value, dict) and isinstance(target[key], dict):
            # (``weights`` is taken whole: merging default engines into a user's partial
            # weight set would change what it sums to.)
            _fill_missing(target[key], value)


def _with_policy_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """Ensure the core and fusion-policy sections are present in the configuration."""
    _fill_missing(config, _base_config())
    config.setdefault("score_normalization", default_normalization_config())
    config.setdefault("fusion_presets", fusion_presets_payload())
    config.setdefault("weight_governance", default_weight_governance_policy())
    config.setdefault("assignment_modes", assignment_modes_payload())
    config.setdefault("advanced", {"hot_reload": True})
    return config


DEFAULT_WEIGHTS: dict[str, float] = _get_default_config()["weights"]
LANGUAGE_BASELINE: dict[str, float] = _get_default_config()["baseline_correction"][
    "baselines"
]


def _finite_scores(evidence: dict[str, Any]) -> dict[str, float]:
    """Numeric, finite scores only (a NaN made ``max()`` order-dependent)."""
    out: dict[str, float] = {}
    for key, value in evidence.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = float(value)
        if math.isfinite(number):
            out[key] = number
    return out


_STRUCTURAL_SIGNALS = ("ast", "logic_flow", "ngram", "winnowing", "token", "fingerprint")


def hard_gate_reason(
    evidence: dict[str, float],
    coverage: float | None = 0.0,
) -> tuple[str | None, str]:
    """Hard gating layer to veto false positives; returns ``(verdict_or_None, reason)``.

    Rules:
    1. If max signal < 0.50: CLEAN (insufficient evidence)
    2. If no structural signals above 0.50: CLEAN
    3. If high similarity but low coverage: CLEAN (few matching lines)
    4. If strong STRUCTURAL similarity but modest coverage: CLEAN

    ``coverage`` is the fraction of code covered by matching segments. ``None`` means it could
    not be computed: the coverage rules are then skipped. (A failed computation used to be
    0.0, which vetoed every pair as CLEAN.)

    Rule 4 now looks at the strongest STRUCTURAL signal. It used the maximum over all signals,
    which includes the embedding score (about 0.7 for unrelated files), so whether a pair was
    vetoed depended on embedding noise.
    """
    scores = _finite_scores(evidence)
    if not scores:
        return "CLEAN", "no usable engine scores"

    if max(scores.values()) < 0.50:
        return "CLEAN", "all engine scores are below 0.50"

    structural_max = max(scores.get(name, 0.0) for name in _STRUCTURAL_SIGNALS)
    if structural_max < 0.50:
        return "CLEAN", "no structural evidence (strongest structural signal below 0.50)"

    if coverage is not None:
        if coverage < 0.15:
            return "CLEAN", f"matching code covers only {coverage:.0%} of the files (below 15%)"
        if structural_max >= 0.80 and coverage < 0.40:
            return "CLEAN", (
                f"high similarity comes from small isolated matches (coverage {coverage:.0%}, below 40%)"
            )

    return None, ""


def hard_gate(
    evidence: dict[str, float],
    coverage: float | None = 0.0,
) -> str | None:
    """Returns ``"CLEAN"`` if the pair is vetoed, else None (see :func:`hard_gate_reason`)."""
    return hard_gate_reason(evidence, coverage)[0]


class FusionEngine:
    """Policy-only fusion engine with evidence aggregation."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._config = load_engine_config()
        self._last_load_time = time.time()
        self._custom_weights = dict(weights) if weights is not None else None

        if weights is None:
            weights = self._config["weights"]

        self.weights: dict[str, float] = self._normalize_weight_names(weights)
        self.baselines: dict[str, float] = self._normalize_weight_names(
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
    def _normalize_weight_names(weights: dict[str, float]) -> dict[str, float]:
        """Map config-facing weight names to FeatureVector engine names."""
        normalized: dict[str, float] = {}
        for name, value in weights.items():
            feature_name = WEIGHT_ALIASES.get(name, name)
            normalized[feature_name] = normalized.get(feature_name, 0.0) + float(value)
        return normalized

    def reload_config(self) -> None:
        """Reload configuration from disk if modified."""
        if self._config.get("advanced", {}).get("hot_reload", True):
            try:
                mtime = os.path.getmtime(CONFIG_PATH)
            except OSError:  # no config file: the defaults stay in force (it used to raise)
                return
            if mtime > self._last_load_time:
                # Weights given at construction are kept (re-running __init__() discarded them).
                self.__init__(self._custom_weights)

    @classmethod
    def get_current_config(cls) -> dict:
        """Get full current engine configuration."""
        return load_engine_config()

    @classmethod
    def update_config(cls, config: dict) -> None:
        """Update and save engine configuration (Admin only)."""
        save_engine_config(config)

    @classmethod
    def get_standard_presets(cls) -> dict[str, dict[str, Any]]:
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
    def get_assignment_presets(cls) -> dict[str, dict[str, Any]]:
        """Get assignment-aware presets with weights and evidence policy."""
        return fusion_presets_payload()

    @classmethod
    def run_calibration_benchmark(cls) -> dict[str, Any]:
        """Run a labeled benchmark and return accuracy metrics.

        Uses the synthetic clone-pair generator so calibration works without
        requiring external datasets. Pair features are extracted through the
        same pipeline used for real submissions.
        """
        try:
            import numpy as np

            from src.backend.benchmark.datasets.synthetic_generator import (
                SyntheticDatasetGenerator,
            )
            from src.backend.benchmark.evaluation.metrics import (
                compute_metrics,
                compute_roc_curve,
            )
            from src.backend.engines.features.feature_extractor import (
                FeatureExtractor,
            )

            started = time.perf_counter()
            generator = SyntheticDatasetGenerator(seed=42)
            dataset = generator.generate_pair_count(
                type1=25, type2=25, type3=25, type4=25, non_clone=100
            )
            extractor = FeatureExtractor()
            engine = cls()  # one engine: it was rebuilt (and the YAML re-read) for every pair
            results = []

            for pair in dataset.pairs:
                features = extractor.extract(pair.code_a, pair.code_b)
                score = engine.fuse(features)
                results.append(
                    {
                        "score": score.final_score,
                        "ground_truth": pair.label,
                    }
                )

            scores = np.array([r["score"] for r in results])
            labels = np.array([r["ground_truth"] for r in results])

            roc_curve = compute_roc_curve(labels, scores)
            # np.trapz was removed in NumPy 2.0 (np.trapezoid replaces it)
            trapezoid = getattr(np, "trapezoid", None) or np.trapz
            roc_auc = float(trapezoid(roc_curve.tpr, roc_curve.fpr))

            # Pick the threshold that maximizes F1 on the ROC curve.
            best_f1 = 0.0
            best_threshold = 0.5
            for threshold in roc_curve.thresholds:
                preds = (scores >= threshold).astype(int)
                m = compute_metrics(labels, preds)
                if m["f1"] > best_f1:
                    best_f1 = m["f1"]
                    best_threshold = float(threshold)

            final_metrics = compute_metrics(
                labels, (scores >= best_threshold).astype(int)
            )

            roc_points = []
            for fpr_val, tpr_val in zip(roc_curve.fpr, roc_curve.tpr):
                roc_points.append({"fpr": float(fpr_val), "tpr": float(tpr_val)})

            return {
                "status": "completed",
                "f1": final_metrics["f1"],
                "precision": final_metrics["precision"],
                "recall": final_metrics["recall"],
                "accuracy": final_metrics["accuracy"],
                "auc_roc": roc_auc,
                "roc_curve": roc_points,
                "optimal_threshold": best_threshold,
                "confusion_matrix": {
                    "tp": final_metrics["tp"],
                    "fp": final_metrics["fp"],
                    "tn": final_metrics["tn"],
                    "fn": final_metrics["fn"],
                },
                "total_pairs": len(results),
                "runtime_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as e:
            logger.exception("Calibration benchmark failed")
            return {"status": "failed", "error": str(e)}

    def fuse(
        self,
        features: FeatureVector,
        weight_multipliers: dict[str, float] | None = None,
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

        # Coverage from the FeatureVector (computed by CodeHighlighter). ``None`` = unknown.
        coverage: float | None = getattr(features, "coverage", None)
        if not getattr(features, "coverage_available", True):
            coverage = None

        # HARD GATE LAYER: Veto false positives before any processing
        veto, veto_reason = hard_gate_reason(raw_scores, coverage=coverage)
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
                # The REAL reason (it always said "No structural evidence / Low signal
                # strength", even for a coverage veto) and no "relevant engines".
                evidence_reasons=[f"Hard gate: {veto_reason}"],
                evidence_guardrails=[f"hard gate: {veto_reason}"],
                evidence_quality=self._calculate_evidence_quality(raw_scores, {}),
                relevant_engines=[],
                verdict="CLEAN",
            )

        shared_regions = self._shared_region_overlap(features)
        ranking = self._rank(raw_scores)

        # Exact match: return 100% for identical files, unless the shared text is the
        # instructor's starter code / boilerplate (two untouched starter files are identical).
        token_score = raw_scores.get("fingerprint", raw_scores.get("token", 0.0))
        if _finite_scores({"t": token_score}).get("t", 0.0) >= 0.95:
            if shared_regions >= STARTER_OVERLAP_CAP:
                return self._shared_region_result(raw_scores, ranking, shared_regions)
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
            FileType,
            apply_weights,
            should_veto_embedding,
        )

        # Apply file-type dependent weights to raw scores
        weighted_scores = apply_weights(raw_scores, file_type)

        # Check if embedding should be vetoed for this file type
        if should_veto_embedding(file_type, file_type_domain):
            weighted_scores["embedding"] = 0.0

        # AGGREGATE: Consolidate to evidence vector (NO scoring)
        # Use weighted scores for evidence aggregation
        evidence = aggregate_from_scores(
            weighted_scores, logic_flow, coverage=0.0 if coverage is None else coverage
        )

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

        guardrails = list(ranking.guardrails) if ranking else []
        reasons = [decision.reason] + (list(ranking.reasons) if ranking else [])
        if shared_regions >= STARTER_OVERLAP_CAP and decision.verdict in ("TRUE", "PROBABLE"):
            # The overlap is mostly starter code / boilerplate: never auto-escalate it.
            decision = Decision(
                verdict="REVIEW",
                confidence=min(decision.confidence, 0.5),
                evidence=decision.evidence,
                reason="shared_starter_or_boilerplate_overlap",
                triggered_layer=decision.triggered_layer,
            )
            guardrails.append("Verdict capped at REVIEW: the overlap is mostly shared starter/boilerplate code.")
            reasons = [decision.reason] + reasons[1:]

        if decision.verdict == "TRUE":
            review_priority = 1.0
        elif decision.verdict == "CLEAN" or ranking is None:
            review_priority = 0.0
        else:
            # PROBABLE / REVIEW used to be 0.0, so the review queue could not order them.
            review_priority = ranking.review_priority

        return FusedScore(
            # final_score is a RISK score: the confidence of a positive verdict, 0.0 for CLEAN.
            # A CLEAN policy decision used to report its 0.95 confidence-in-clean here, which
            # ranked "clean" pairs above everything else in score-ordered consumers (the
            # calibration benchmark thresholds this value).
            final_score=0.0 if decision.verdict == "CLEAN" else decision.confidence,
            confidence=decision.confidence,
            uncertainty=1.0 - decision.confidence,
            agreement_index=decision.confidence,
            components=raw_scores,
            contributions={},
            review_priority=review_priority,
            professor_summary=f"Policy Decision: {decision.verdict}",
            evidence_reasons=reasons,
            evidence_guardrails=guardrails,
            evidence_quality=self._calculate_evidence_quality(
                raw_scores, relevant_scores
            ),
            relevant_engines=list(relevant_scores.keys()),
            verdict=decision.verdict,
        )

    def _rank(self, raw_scores: dict[str, float]):
        """Evidence-ranker output (guardrails, reasons, review priority); None on failure."""
        try:
            return self._ranker.rank_pair(raw_scores)
        except Exception as exc:  # the ranker informs the result, it must not break it
            logger.warning("Evidence ranker failed: %s", exc)
            return None

    @staticmethod
    def _shared_region_overlap(features: Any) -> float:
        """How much of the match is instructor starter code / boilerplate (0..1)."""
        values = []
        for name in ("starter_code_overlap", "boilerplate_overlap"):
            value = getattr(features, name, 0.0)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                values.append(float(value))
        return max(values, default=0.0)

    def _shared_region_result(self, raw_scores: dict[str, float], ranking: Any, overlap: float) -> FusedScore:
        return FusedScore(
            final_score=0.5,
            confidence=0.5,
            uncertainty=0.5,
            agreement_index=0.5,
            components=raw_scores,
            contributions={},
            review_priority=ranking.review_priority if ranking else 0.0,
            professor_summary="Policy Decision: REVIEW",
            evidence_reasons=["shared_starter_or_boilerplate_overlap"]
            + (list(ranking.reasons) if ranking else []),
            evidence_guardrails=[
                f"Identical text is mostly shared starter/boilerplate code ({overlap:.0%}); not escalated."
            ]
            + (list(ranking.guardrails) if ranking else []),
            evidence_quality={"fingerprint": "conclusive"},
            relevant_engines=["fingerprint"],
            verdict="REVIEW",
        )

    def get_weights(self) -> dict[str, float]:
        """Return the current normalized engine weights."""
        return dict(self.weights)

    def set_weights(self, weights: dict[str, float]) -> None:
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
        raw_scores: dict[str, float], corrected_scores: dict[str, float]
    ) -> dict[str, str]:
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
