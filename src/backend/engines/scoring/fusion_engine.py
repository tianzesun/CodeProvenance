"""Fusion Engine - Combined multi-engine scoring with configurable weights."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

import yaml

from src.backend.evaluation.arbitration import BayesianArbitrator

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


# Baseline scores expected for two unrelated files in the same language.
# These represent the "noise floor" — scores that occur just from sharing
# a language's syntax, common patterns, and embedding vocabulary.
# Scores at or below baseline are treated as zero similarity.
LANGUAGE_BASELINE: Dict[str, float] = {
    "embedding": 0.70,  # UniXcoder sees "this is Python code" for both
    "winnowing": 0.25,  # Common keywords/structures produce some overlap
    "ngram": 0.15,  # Character n-grams share syntax tokens
    "ast": 0.25,  # Similar AST node types (functions, returns, etc.)
    "fingerprint": 0.15,  # Token-level overlap from language keywords
}

WEIGHT_ALIASES: Dict[str, str] = {
    "token": "fingerprint",
    "semantic": "embedding",
    "codebert": "embedding",
    "gst": "ngram",
}


CONFIG_PATH = Path(__file__).parent.parent / "engine_weights.yaml"


def load_engine_config() -> Dict:
    """Load engine configuration from YAML config file."""
    if not CONFIG_PATH.exists():
        return _get_default_config()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    except Exception:
        return _get_default_config()


def save_engine_config(config: Dict) -> None:
    """Save engine configuration to YAML config file with validation."""
    # Validate weights sum correctly
    if "weights" in config:
        total = sum(config["weights"].values())
        if abs(total - 1.0) > 0.001:
            # Normalize weights automatically
            config["weights"] = {
                k: round(v / total, 4) for k, v in config["weights"].items()
            }

    # Validate all values are within 0-1 range
    for section in ["weights", "baseline_correction"]:
        if section in config:
            for key, value in config[section].items():
                if isinstance(value, (int, float)):
                    config[section][key] = max(0.0, min(1.0, value))

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)


def _get_default_config() -> Dict:
    return {
        "weights": {
            "ast": 0.65,
            "token": 0.25,
            "winnowing": 0.10,
            "graph": 0.00,
            "execution": 0.00,
            "embedding": 0.00,
            "ngram": 0.00,
            "codebert": 0.00,
        },
        "baseline_correction": {
            "enabled": True,
            "baselines": {
                "embedding": 0.70,
                "winnowing": 0.25,
                "ngram": 0.15,
                "ast": 0.25,
                "fingerprint": 0.15,
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


# Default fallback values
DEFAULT_WEIGHTS: Dict[str, float] = _get_default_config()["weights"]
LANGUAGE_BASELINE: Dict[str, float] = _get_default_config()["baseline_correction"][
    "baselines"
]


class FusionEngine:
    """Multi-engine fusion scoring authority.

    Combines similarity scores from multiple engines using
    configurable weights and produces a single fused score.

    Applies baseline correction to remove same-language noise floor
    so that unrelated files score near 0% instead of 30-50%.
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
        self._arbitrator = BayesianArbitrator(
            engine_prior_precisions={k: v * multiplier for k, v in self.weights.items()}
        )

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
    def get_standard_presets(cls) -> Dict[str, Dict[str, float]]:
        """Get standard faculty presets.

        These are safe multipliers that overlay on base weights, they do
        not modify the admin calibrated base configuration.
        """
        return {
            "default": {
                "name": "Balanced",
                "description": "Default balanced detection profile. Good for most assignments.",
                "multipliers": {},
            },
            "strict_copy": {
                "name": "Strict Copy Detection",
                "description": "For introductory assignments. Emphasizes exact matching.",
                "multipliers": {
                    "winnowing": 2.0,
                    "token": 1.5,
                    "ast": 0.5,
                    "graph": 0.5,
                },
            },
            "semantic_plagiarism": {
                "name": "Advanced Plagiarism Detection",
                "description": "For advanced assignments. Detects obfuscation and modification.",
                "multipliers": {
                    "graph": 2.0,
                    "execution": 1.8,
                    "ast": 1.2,
                    "winnowing": 0.5,
                },
            },
            "structure_focus": {
                "name": "Code Structure Focus",
                "description": "Prioritize architecture and design similarity over exact code.",
                "multipliers": {
                    "ast": 1.8,
                    "graph": 1.5,
                    "token": 0.5,
                    "winnowing": 0.5,
                },
            },
            "ai_detection": {
                "name": "AI Generated Code Detection",
                "description": "Optimize for detecting AI generated code patterns.",
                "multipliers": {
                    "embedding": 3.0,
                    "ast": 1.2,
                },
            },
        }

    @classmethod
    def run_calibration_benchmark(cls) -> Dict[str, Any]:
        """Run standard benchmark dataset and return accuracy metrics for current weights.

        Runs against standard IR-Plag test set with 2100 known pairs.
        Returns full accuracy metrics including F1, precision, recall, ROC curve.
        """
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

    @classmethod
    def calibrate_optimal_weights(
        cls, use_optuna: bool = True, n_trials: int = 100
    ) -> Dict[str, Any]:
        """Automatically calibrate engine weights to maximize F1 score.

        Uses Bayesian optimization via Optuna over standard benchmark dataset
        to find optimal weight combination. Falls back to heuristic tuning if
        Optuna is not available. Returns best found configuration and persists
        results to engine_weights.yaml config file.

        Args:
            use_optuna: Use Optuna Bayesian optimization (default: True)
            n_trials: Number of optimization trials for Optuna

        Returns:
            Calibration results with updated weights and performance metrics
        """
        from src.backend.evaluation.benchmark_tribunal import BenchmarkTribunal

        config = load_engine_config()

        if use_optuna:
            try:
                import optuna
                from src.backend.benchmark.datasets.ir_plag import IRPlagDataset
                from src.backend.evaluation.metrics import calculate_accuracy_metrics

                dataset = IRPlagDataset()
                engine_names = list(config["weights"].keys())

                def objective(trial: optuna.Trial) -> float:
                    # Suggest weights for each engine
                    weights = {}
                    for engine in engine_names:
                        weights[engine] = trial.suggest_float(
                            engine, 0.01, 1.0, log=False
                        )

                    # Normalize weights to sum 1.0
                    total = sum(weights.values())
                    normalized_weights = {k: v / total for k, v in weights.items()}

                    # Evaluate this weight configuration
                    engine = cls(weights=normalized_weights)
                    results = []

                    for pair in dataset.test_pairs:
                        score = engine.fuse(pair.features)
                        results.append(
                            {
                                "score": score.final_score,
                                "ground_truth": pair.is_plagiarized,
                            }
                        )

                    metrics = calculate_accuracy_metrics(results)
                    return metrics.f1

                # Run optimization
                study = optuna.create_study(
                    direction="maximize", sampler=optuna.samplers.TPESampler(seed=42)
                )
                study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

                # Get best weights
                best_weights = study.best_params
                total = sum(best_weights.values())
                config["weights"] = {
                    k: round(v / total, 4) for k, v in best_weights.items()
                }

                best_f1 = study.best_value
                trial_count = len(study.trials)

            except (ImportError, Exception):
                # Fall back to heuristic calibration if Optuna fails
                use_optuna = False

        if not use_optuna:
            # Original heuristic calibration method
            tribunal = BenchmarkTribunal()
            result = tribunal.run()

            engine_performance = {}
            for engine, metrics in result.engine_scores.items():
                if engine in config["weights"]:
                    engine_performance[engine] = metrics.f1

            total_score = sum(engine_performance.values())
            if total_score > 0:
                for engine, score in engine_performance.items():
                    config["weights"][engine] = round(score / total_score, 4)

            best_f1 = result.overall_f1
            trial_count = 1

            # Update baseline values from calibration results
            for engine, baseline in result.baseline_estimates.items():
                if engine in config["baseline_correction"]["baselines"]:
                    config["baseline_correction"]["baselines"][engine] = round(
                        baseline, 4
                    )

            # Update decision threshold for optimal F1
            config["decision"]["default_threshold"] = round(result.optimal_threshold, 4)

            # Update all calibrated thresholds
            if "thresholds" not in config:
                config["thresholds"] = {}

            config["thresholds"]["high_similarity"] = round(result.thresholds.high, 4)
            config["thresholds"]["medium_similarity"] = round(
                result.thresholds.medium, 4
            )
            config["thresholds"]["low_similarity"] = round(result.thresholds.low, 4)
            config["thresholds"]["identical"] = round(result.thresholds.identical, 4)

        # Record calibration metadata
        if "advanced" not in config:
            config["advanced"] = {}

        config["advanced"]["last_calibration_time"] = int(time.time())
        config["advanced"]["calibration_method"] = (
            "optuna" if use_optuna else "heuristic"
        )
        config["advanced"]["calibration_trials"] = trial_count
        config["advanced"]["best_f1_score"] = round(best_f1, 4)

        # Persist updated configuration to yaml file
        save_engine_config(config)

        # Reload instance with new values
        cls.__init__(cls)

        return {
            "method": "optuna" if use_optuna else "heuristic",
            "updated_weights": config["weights"],
            "updated_baselines": config["baseline_correction"]["baselines"],
            "optimal_threshold": config["decision"]["default_threshold"],
            "f1_score": round(best_f1, 4),
            "trials_completed": trial_count,
        }

    def fuse(
        self,
        features: "FeatureVector",
        weight_multipliers: Optional[Dict[str, float]] = None,
    ) -> FusedScore:
        """Combine engine outputs into a single similarity score using Bayesian arbitration.

        Applies baseline correction: subtracts the expected same-language noise floor
        from each engine score before fusion. This prevents unrelated files from
        scoring 30-50% just because they share a programming language.

        Args:
            features: A FeatureVector containing scores from each engine.
            weight_multipliers: Optional per-engine multipliers to overlay on base weights.
                Used for user presets, does not modify base configuration.

        Returns:
            A FusedScore with the combined score, confidence, and per-engine breakdown.
        """
        raw_scores = features.as_dict()

        # Apply user preset weight multipliers if provided
        active_weights = dict(self.weights)
        if weight_multipliers:
            for engine, multiplier in weight_multipliers.items():
                if engine in active_weights:
                    active_weights[engine] *= multiplier

        # Re-normalize after multipliers
        total = sum(active_weights.values())
        if total > 0:
            active_weights = {k: v / total for k, v in active_weights.items()}

        # Apply baseline correction — subtract noise floor from each engine
        corrected_scores = {}
        for name, score in raw_scores.items():
            baseline = self.baselines.get(name, LANGUAGE_BASELINE.get(name, 0.0))
            corrected = max(0.0, score - baseline) / max(0.01, 1.0 - baseline)
            corrected_scores[name] = round(corrected, 4)

        arbitration = self._arbitrator.arbitrate(corrected_scores)

        final_score = arbitration.fused_score

        # Clamp to valid range
        final_score = min(1.0, max(0.0, final_score))
        final_score = self._apply_precision_guards(corrected_scores, final_score)

        return FusedScore(
            final_score=final_score,
            confidence=arbitration.agreement_index,
            uncertainty=arbitration.uncertainty,
            agreement_index=arbitration.agreement_index,
            components=raw_scores,
            contributions=arbitration.engine_contributions,
        )

    def _apply_precision_guards(
        self, corrected_scores: Dict[str, float], final_score: float
    ) -> float:
        """Cap high-risk scores when evidence comes from too few concrete engines."""
        guard = self._config.get("precision_guard", {})
        if not guard.get("enabled", True):
            return final_score

        high_score_floor = float(guard.get("high_score_floor", 0.72))
        if final_score < high_score_floor:
            return final_score

        evidence_threshold = float(guard.get("evidence_threshold", 0.35))
        lexical_threshold = float(guard.get("lexical_threshold", 0.35))
        minimum_concrete_engines = int(guard.get("minimum_concrete_engines", 2))
        minimum_lexical_engines = int(guard.get("minimum_lexical_engines", 1))
        cap = float(guard.get("insufficient_evidence_cap", 0.58))
        semantic_only_cap = float(guard.get("semantic_only_cap", 0.45))

        concrete_engines = ("ast", "fingerprint", "winnowing", "ngram")
        lexical_engines = ("fingerprint", "winnowing", "ngram")
        concrete_evidence = sum(
            1
            for name in concrete_engines
            if corrected_scores.get(name, 0.0) >= evidence_threshold
        )
        lexical_evidence = sum(
            1
            for name in lexical_engines
            if corrected_scores.get(name, 0.0) >= lexical_threshold
        )

        if concrete_evidence < minimum_concrete_engines:
            return min(final_score, cap)
        if lexical_evidence < minimum_lexical_engines:
            return min(final_score, semantic_only_cap)
        return final_score

    def get_weights(self) -> Dict[str, float]:
        """Return the current normalized engine weights."""
        return dict(self.weights)

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Update and re-normalize engine weights.

        Args:
            weights: A dict mapping engine names to raw weight values.
        """
        self.weights = self._normalize_weight_names(weights)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        self._arbitrator = BayesianArbitrator(
            engine_prior_precisions={k: v * 20 for k, v in self.weights.items()}
        )
