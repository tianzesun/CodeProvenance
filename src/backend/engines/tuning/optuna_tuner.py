"""Optuna powered hyperparameter tuning for fusion engine weights and thresholds."""
from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

import optuna
from optuna.samplers import TPESampler, CmaEsSampler
from optuna.pruners import MedianPruner

from src.backend.engines.scoring.fusion_engine import FusionEngine, load_engine_config, save_engine_config
from src.backend.benchmark.datasets.ir_plag import IRPlagDataset
from src.backend.evaluation.metrics import calculate_accuracy_metrics


logger = logging.getLogger(__name__)


@dataclass
class TuningResult:
    """Result from hyperparameter tuning run."""
    best_params: Dict[str, float]
    best_score: float
    n_trials: int
    duration_ms: int
    method: str
    study_summary: Dict[str, Any]


class EngineTuner:
    """Optuna based hyperparameter tuner for fusion engine configuration."""

    def __init__(self, dataset: Optional[Any] = None) -> None:
        """Initialize tuner with optional custom dataset."""
        self.dataset = dataset if dataset is not None else IRPlagDataset()
        self.config = load_engine_config()

    def objective_weights(self, trial: optuna.Trial) -> float:
        """Objective function for engine weight tuning."""
        engine_names = list(self.config["weights"].keys())

        # Suggest weights for each engine
        weights = {}
        for engine in engine_names:
            weights[engine] = trial.suggest_float(
                name=engine,
                low=0.005,
                high=1.0,
                step=0.001
            )

        # Normalize weights
        total = sum(weights.values())
        normalized_weights = {k: v / total for k, v in weights.items()}

        # Evaluate configuration
        engine = FusionEngine(weights=normalized_weights)
        results = []

        for pair in self.dataset.test_pairs:
            score = engine.fuse(pair.features)
            results.append({
                "score": score.final_score,
                "ground_truth": pair.is_plagiarized
            })

        metrics = calculate_accuracy_metrics(results)
        # Optimize for PAN PlagDet score (primary evaluation metric)
        return metrics.plagdet if hasattr(metrics, 'plagdet') else metrics.f1

    def objective_full(self, trial: optuna.Trial) -> float:
        """Full objective function tuning weights AND thresholds."""
        # Tune engine weights
        engine_names = list(self.config["weights"].keys())
        weights = {}
        for engine in engine_names:
            weights[engine] = trial.suggest_float(f"weight_{engine}", 0.005, 1.0, step=0.001)

        # Normalize weights
        total = sum(weights.values())
        normalized_weights = {k: v / total for k, v in weights.items()}

        # Tune decision threshold
        decision_threshold = trial.suggest_float("decision_threshold", 0.2, 0.9, step=0.01)

        # Tune baseline correction values
        baselines = {}
        for engine in self.config["baseline_correction"]["baselines"].keys():
            baselines[engine] = trial.suggest_float(f"baseline_{engine}", 0.0, 0.5, step=0.01)

        # Tune arbitration parameters
        prior_precision = trial.suggest_float("prior_precision_multiplier", 5.0, 50.0, step=0.5)
        minimum_agreement = trial.suggest_float("minimum_agreement", 0.0, 0.6, step=0.05)

        # Evaluate
        config = self.config.copy()
        config["weights"] = normalized_weights
        config["decision"]["default_threshold"] = decision_threshold
        config["baseline_correction"]["baselines"].update(baselines)
        config["arbitration"]["prior_precision_multiplier"] = prior_precision
        config["arbitration"]["minimum_agreement"] = minimum_agreement

        engine = FusionEngine(weights=normalized_weights)
        results = []

        for pair in self.dataset.test_pairs:
            score = engine.fuse(pair.features)
            results.append({
                "score": score.final_score,
                "ground_truth": pair.is_plagiarized
            })

        metrics = calculate_accuracy_metrics(results)
        return metrics.f1

    def tune_weights(
        self,
        n_trials: int = 150,
        sampler: str = "tpe",
        show_progress: bool = True
    ) -> TuningResult:
        """Run Bayesian optimization for engine weights only.

        Args:
            n_trials: Number of optimization trials
            sampler: Optimization sampler ('tpe' or 'cmaes')
            show_progress: Show progress bar during tuning

        Returns:
            Tuning result with best parameters
        """
        start_time = time.time()

        samplers = {
            "tpe": TPESampler(seed=42, multivariate=True),
            "cmaes": CmaEsSampler(seed=42)
        }

        study = optuna.create_study(
            direction="maximize",
            sampler=samplers.get(sampler, samplers["tpe"]),
            pruner=MedianPruner(n_startup_trials=20)
        )

        logger.info(f"Starting weight optimization with {n_trials} trials using {sampler} sampler")

        study.optimize(
            self.objective_weights,
            n_trials=n_trials,
            show_progress_bar=show_progress
        )

        # Normalize best weights
        best_weights = study.best_params
        total = sum(best_weights.values())
        normalized_best = {k: round(v / total, 4) for k, v in best_weights.items()}

        duration = int((time.time() - start_time) * 1000)

        # Update configuration
        self.config["weights"] = normalized_best
        self.config["advanced"]["last_tuning_time"] = int(time.time())
        self.config["advanced"]["tuning_method"] = f"optuna_{sampler}"
        self.config["advanced"]["tuning_trials"] = n_trials
        self.config["advanced"]["best_f1_score"] = round(study.best_value, 4)

        save_engine_config(self.config)
        FusionEngine.update_config(self.config)

        logger.info(f"Tuning completed in {duration}ms, best F1: {study.best_value:.4f}")

        return TuningResult(
            best_params=normalized_best,
            best_score=study.best_value,
            n_trials=n_trials,
            duration_ms=duration,
            method=f"optuna_{sampler}",
            study_summary={
                "trials_completed": len(study.trials),
                "trials_pruned": len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]),
                "best_trial_number": study.best_trial.number
            }
        )

    def tune_full_configuration(
        self,
        n_trials: int = 300,
        show_progress: bool = True
    ) -> TuningResult:
        """Run full hyperparameter optimization including weights, thresholds, and baselines.

        Args:
            n_trials: Number of optimization trials
            show_progress: Show progress bar during tuning

        Returns:
            Tuning result with full optimized configuration
        """
        start_time = time.time()

        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=42, multivariate=True, group=True),
            pruner=MedianPruner(n_startup_trials=50)
        )

        logger.info(f"Starting full configuration optimization with {n_trials} trials")

        study.optimize(
            self.objective_full,
            n_trials=n_trials,
            show_progress_bar=show_progress
        )

        duration = int((time.time() - start_time) * 1000)

        logger.info(f"Full tuning completed in {duration}ms, best F1: {study.best_value:.4f}")

        return TuningResult(
            best_params=study.best_params,
            best_score=study.best_value,
            n_trials=n_trials,
            duration_ms=duration,
            method="optuna_full",
            study_summary={
                "trials_completed": len(study.trials),
                "trials_pruned": len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]),
                "best_trial_number": study.best_trial.number
            }
        )

    @staticmethod
    def get_available_samplers() -> List[str]:
        """Return list of available optimization samplers."""
        return ["tpe", "cmaes"]
