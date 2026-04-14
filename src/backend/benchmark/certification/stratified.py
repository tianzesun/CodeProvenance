"""Stratified analysis for certification reports.

Provides breakdown of results across different dimensions:
- Clone Type (I-IV): Shows robustness to different clone types
- Difficulty: Shows resistance to obfuscation
- Language: Shows generalization across programming languages
- Dataset: Shows consistency across different datasets

This is a key competitive advantage - most tools don't provide stratified analysis.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from .models import BenchmarkRecord, EngineMetrics, filter_records, group_records_by_engine
from .confidence_intervals import bootstrap_ci, ConfidenceInterval


@dataclass(frozen=True)
class StratifiedMetrics:
    """Metrics for a specific stratum (slice).

    Attributes:
        stratum_name: Name of the stratum (e.g., "Type I", "HARD").
        stratum_value: Value of the stratum (e.g., 1, "HARD").
        n_samples: Number of samples in this stratum.
        precision: Precision score.
        recall: Recall score.
        f1: F1 score.
        accuracy: Accuracy score.
        ci_precision: Confidence interval for precision.
        ci_recall: Confidence interval for recall.
        ci_f1: Confidence interval for F1.
    """
    stratum_name: str
    stratum_value: Union[int, str]
    n_samples: int
    precision: float
    recall: float
    f1: float
    accuracy: float
    ci_precision: Tuple[float, float] = (0.0, 0.0)
    ci_recall: Tuple[float, float] = (0.0, 0.0)
    ci_f1: Tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stratum_name": self.stratum_name,
            "stratum_value": self.stratum_value,
            "n_samples": self.n_samples,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "accuracy": self.accuracy,
            "ci_precision": list(self.ci_precision),
            "ci_recall": list(self.ci_recall),
            "ci_f1": list(self.ci_f1),
        }


@dataclass
class StratifiedResults:
    """Complete stratified analysis results.

    Attributes:
        engine_name: Name of the engine.
        overall_metrics: Overall metrics across all strata.
        by_clone_type: Metrics broken down by clone type.
        by_difficulty: Metrics broken down by difficulty.
        by_language: Metrics broken down by language.
        degradation_analysis: Analysis of performance degradation.
    """
    engine_name: str
    overall_metrics: EngineMetrics
    by_clone_type: Dict[int, StratifiedMetrics] = field(default_factory=dict)
    by_difficulty: Dict[str, StratifiedMetrics] = field(default_factory=dict)
    by_language: Dict[str, StratifiedMetrics] = field(default_factory=dict)
    degradation_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_name": self.engine_name,
            "overall_metrics": self.overall_metrics.to_dict(),
            "by_clone_type": {k: v.to_dict() for k, v in self.by_clone_type.items()},
            "by_difficulty": {k: v.to_dict() for k, v in self.by_difficulty.items()},
            "by_language": {k: v.to_dict() for k, v in self.by_language.items()},
            "degradation_analysis": self.degradation_analysis,
        }


def compute_metrics_from_records(
    records: List[BenchmarkRecord],
    engine_name: str = "engine",
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> EngineMetrics:
    """Compute metrics from benchmark records.

    Args:
        records: List of benchmark records.
        engine_name: Name of the engine.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level for CIs.
        seed: Random seed.

    Returns:
        EngineMetrics with computed metrics and confidence intervals.
    """
    if not records:
        return EngineMetrics(
            engine_name=engine_name,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            accuracy=0.0,
            n_samples=0,
        )

    # Extract labels and decisions
    labels = np.array([r.label for r in records])
    decisions = np.array([r.decision for r in records])

    # Compute confusion matrix
    tp = np.sum((labels == 1) & (decisions == True))
    fp = np.sum((labels == 0) & (decisions == True))
    fn = np.sum((labels == 1) & (decisions == False))
    tn = np.sum((labels == 0) & (decisions == False))

    # Compute metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(records) if len(records) > 0 else 0.0

    # Compute confidence intervals using bootstrap
    def precision_fn(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        tp = np.sum((y_true == 1) & (y_pred == True))
        fp = np.sum((y_true == 0) & (y_pred == True))
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0

    def recall_fn(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        tp = np.sum((y_true == 1) & (y_pred == True))
        fn = np.sum((y_true == 1) & (y_pred == False))
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0

    def f1_fn(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        tp = np.sum((y_true == 1) & (y_pred == True))
        fp = np.sum((y_true == 0) & (y_pred == True))
        fn = np.sum((y_true == 1) & (y_pred == False))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

    # Bootstrap CIs (if enough samples)
    ci_precision = (precision, precision)
    ci_recall = (recall, recall)
    ci_f1 = (f1, f1)

    if len(records) >= 30 and n_bootstrap > 0:
        try:
            prec_ci = bootstrap_ci(labels, decisions, precision_fn, n_bootstrap, confidence_level, seed)
            ci_precision = (prec_ci.ci_lower, prec_ci.ci_upper)

            rec_ci = bootstrap_ci(labels, decisions, recall_fn, n_bootstrap, confidence_level, seed)
            ci_recall = (rec_ci.ci_lower, rec_ci.ci_upper)

            f1_ci = bootstrap_ci(labels, decisions, f1_fn, n_bootstrap, confidence_level, seed)
            ci_f1 = (f1_ci.ci_lower, f1_ci.ci_upper)
        except Exception:
            pass  # Fall back to point estimates

    return EngineMetrics(
        engine_name=engine_name,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        n_samples=len(records),
        n_positive=int(np.sum(labels == 1)),
        n_negative=int(np.sum(labels == 0)),
        ci_precision=ci_precision,
        ci_recall=ci_recall,
        ci_f1=ci_f1,
    )


def compute_stratified_metrics(
    records: List[BenchmarkRecord],
    stratum_name: str,
    stratum_value: Union[int, str],
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> StratifiedMetrics:
    """Compute metrics for a specific stratum.

    Args:
        records: List of benchmark records for this stratum.
        stratum_name: Name of the stratum.
        stratum_value: Value of the stratum.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level.
        seed: Random seed.

    Returns:
        StratifiedMetrics for this stratum.
    """
    if not records:
        return StratifiedMetrics(
            stratum_name=stratum_name,
            stratum_value=stratum_value,
            n_samples=0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            accuracy=0.0,
        )

    # Extract labels and decisions
    labels = np.array([r.label for r in records])
    decisions = np.array([r.decision for r in records])

    # Compute confusion matrix
    tp = np.sum((labels == 1) & (decisions == True))
    fp = np.sum((labels == 0) & (decisions == True))
    fn = np.sum((labels == 1) & (decisions == False))
    tn = np.sum((labels == 0) & (decisions == False))

    # Compute metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(records) if len(records) > 0 else 0.0

    # Compute confidence intervals (if enough samples)
    ci_precision = (precision, precision)
    ci_recall = (recall, recall)
    ci_f1 = (f1, f1)

    if len(records) >= 30 and n_bootstrap > 0:
        try:
            def f1_fn(y_true: np.ndarray, y_pred: np.ndarray) -> float:
                tp = np.sum((y_true == 1) & (y_pred == True))
                fp = np.sum((y_true == 0) & (y_pred == True))
                fn = np.sum((y_true == 1) & (y_pred == False))
                prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

            f1_ci = bootstrap_ci(labels, decisions, f1_fn, n_bootstrap, confidence_level, seed)
            ci_f1 = (f1_ci.ci_lower, f1_ci.ci_upper)
        except Exception:
            pass

    return StratifiedMetrics(
        stratum_name=stratum_name,
        stratum_value=stratum_value,
        n_samples=len(records),
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        ci_precision=ci_precision,
        ci_recall=ci_recall,
        ci_f1=ci_f1,
    )


class StratifiedAnalyzer:
    """Analyzer for stratified results across multiple dimensions.

    Provides comprehensive breakdown of engine performance across:
    - Clone types (I-IV)
    - Difficulty levels (EASY, HARD, EXPERT)
    - Programming languages
    """

    def __init__(
        self,
        n_bootstrap: int = 1000,
        confidence_level: float = 0.95,
        seed: int = 42,
    ) -> None:
        """Initialize stratified analyzer.

        Args:
            n_bootstrap: Number of bootstrap samples for CIs.
            confidence_level: Confidence level for intervals.
            seed: Random seed for reproducibility.
        """
        self.n_bootstrap = n_bootstrap
        self.confidence_level = confidence_level
        self.seed = seed

    def analyze(
        self,
        records: List[BenchmarkRecord],
        engine_name: str = "engine",
    ) -> StratifiedResults:
        """Perform stratified analysis.

        Args:
            records: List of benchmark records.
            engine_name: Name of the engine.

        Returns:
            StratifiedResults with breakdown across all dimensions.
        """
        if not records:
            return StratifiedResults(
                engine_name=engine_name,
                overall_metrics=EngineMetrics(
                    engine_name=engine_name,
                    precision=0.0,
                    recall=0.0,
                    f1=0.0,
                    accuracy=0.0,
                    n_samples=0,
                ),
            )

        # Compute overall metrics
        overall_metrics = compute_metrics_from_records(
            records, engine_name, self.n_bootstrap, self.confidence_level, self.seed
        )

        # Analyze by clone type
        by_clone_type = self._analyze_by_clone_type(records)

        # Analyze by difficulty
        by_difficulty = self._analyze_by_difficulty(records)

        # Analyze by language
        by_language = self._analyze_by_language(records)

        # Compute degradation analysis
        degradation_analysis = self._compute_degradation(by_clone_type, by_difficulty)

        return StratifiedResults(
            engine_name=engine_name,
            overall_metrics=overall_metrics,
            by_clone_type=by_clone_type,
            by_difficulty=by_difficulty,
            by_language=by_language,
            degradation_analysis=degradation_analysis,
        )

    def _analyze_by_clone_type(
        self, records: List[BenchmarkRecord]
    ) -> Dict[int, StratifiedMetrics]:
        """Analyze results by clone type.

        Args:
            records: List of benchmark records.

        Returns:
            Dictionary mapping clone type to metrics.
        """
        results = {}

        # Group by clone type
        for clone_type in range(5):  # 0-4 (0 = non-clone)
            filtered = [r for r in records if r.clone_type == clone_type]
            if filtered:
                metrics = compute_stratified_metrics(
                    filtered,
                    "clone_type",
                    clone_type,
                    self.n_bootstrap,
                    self.confidence_level,
                    self.seed,
                )
                results[clone_type] = metrics

        return results

    def _analyze_by_difficulty(
        self, records: List[BenchmarkRecord]
    ) -> Dict[str, StratifiedMetrics]:
        """Analyze results by difficulty level.

        Args:
            records: List of benchmark records.

        Returns:
            Dictionary mapping difficulty to metrics.
        """
        results = {}

        # Group by difficulty
        difficulties = set(r.difficulty for r in records)
        for difficulty in difficulties:
            filtered = [r for r in records if r.difficulty == difficulty]
            if filtered:
                metrics = compute_stratified_metrics(
                    filtered,
                    "difficulty",
                    difficulty,
                    self.n_bootstrap,
                    self.confidence_level,
                    self.seed,
                )
                results[difficulty] = metrics

        return results

    def _analyze_by_language(
        self, records: List[BenchmarkRecord]
    ) -> Dict[str, StratifiedMetrics]:
        """Analyze results by programming language.

        Args:
            records: List of benchmark records.

        Returns:
            Dictionary mapping language to metrics.
        """
        results = {}

        # Group by language
        languages = set(r.language for r in records)
        for language in languages:
            filtered = [r for r in records if r.language == language]
            if filtered:
                metrics = compute_stratified_metrics(
                    filtered,
                    "language",
                    language,
                    self.n_bootstrap,
                    self.confidence_level,
                    self.seed,
                )
                results[language] = metrics

        return results

    def _compute_degradation(
        self,
        by_clone_type: Dict[int, StratifiedMetrics],
        by_difficulty: Dict[str, StratifiedMetrics],
    ) -> Dict[str, Any]:
        """Compute performance degradation analysis.

        Analyzes how performance degrades as clone type increases (Type I → IV)
        and as difficulty increases (EASY → HARD → EXPERT).

        Args:
            by_clone_type: Metrics by clone type.
            by_difficulty: Metrics by difficulty.

        Returns:
            Dictionary with degradation analysis.
        """
        degradation = {}

        # Clone type degradation (Type I → IV)
        clone_f1_scores = []
        for clone_type in [1, 2, 3, 4]:
            if clone_type in by_clone_type:
                clone_f1_scores.append(by_clone_type[clone_type].f1)

        if len(clone_f1_scores) >= 2:
            degradation["clone_type"] = {
                "type_1_f1": clone_f1_scores[0] if len(clone_f1_scores) > 0 else 0.0,
                "type_4_f1": clone_f1_scores[-1] if len(clone_f1_scores) > 0 else 0.0,
                "degradation": clone_f1_scores[0] - clone_f1_scores[-1] if len(clone_f1_scores) > 1 else 0.0,
                "degradation_pct": (
                    (clone_f1_scores[0] - clone_f1_scores[-1]) / clone_f1_scores[0] * 100
                    if len(clone_f1_scores) > 1 and clone_f1_scores[0] > 0
                    else 0.0
                ),
            }

        # Difficulty degradation (EASY → HARD → EXPERT)
        difficulty_order = ["EASY", "HARD", "EXPERT"]
        difficulty_f1_scores = []
        for diff in difficulty_order:
            if diff in by_difficulty:
                difficulty_f1_scores.append(by_difficulty[diff].f1)

        if len(difficulty_f1_scores) >= 2:
            degradation["difficulty"] = {
                "easy_f1": difficulty_f1_scores[0] if len(difficulty_f1_scores) > 0 else 0.0,
                "expert_f1": difficulty_f1_scores[-1] if len(difficulty_f1_scores) > 0 else 0.0,
                "degradation": difficulty_f1_scores[0] - difficulty_f1_scores[-1] if len(difficulty_f1_scores) > 1 else 0.0,
                "degradation_pct": (
                    (difficulty_f1_scores[0] - difficulty_f1_scores[-1]) / difficulty_f1_scores[0] * 100
                    if len(difficulty_f1_scores) > 1 and difficulty_f1_scores[0] > 0
                    else 0.0
                ),
            }

        return degradation


def compare_stratified_results(
    results_a: StratifiedResults,
    results_b: StratifiedResults,
) -> Dict[str, Any]:
    """Compare stratified results between two engines.

    Args:
        results_a: Stratified results from engine A.
        results_b: Stratified results from engine B.

    Returns:
        Dictionary with comparison across all strata.
    """
    comparison = {
        "engine_a": results_a.engine_name,
        "engine_b": results_b.engine_name,
        "overall": {
            "f1_diff": results_a.overall_metrics.f1 - results_b.overall_metrics.f1,
            "precision_diff": results_a.overall_metrics.precision - results_b.overall_metrics.precision,
            "recall_diff": results_a.overall_metrics.recall - results_b.overall_metrics.recall,
        },
        "by_clone_type": {},
        "by_difficulty": {},
        "by_language": {},
    }

    # Compare by clone type
    for clone_type in set(results_a.by_clone_type.keys()) | set(results_b.by_clone_type.keys()):
        metrics_a = results_a.by_clone_type.get(clone_type)
        metrics_b = results_b.by_clone_type.get(clone_type)

        if metrics_a and metrics_b:
            comparison["by_clone_type"][clone_type] = {
                "f1_diff": metrics_a.f1 - metrics_b.f1,
                "engine_a_f1": metrics_a.f1,
                "engine_b_f1": metrics_b.f1,
            }

    # Compare by difficulty
    for difficulty in set(results_a.by_difficulty.keys()) | set(results_b.by_difficulty.keys()):
        metrics_a = results_a.by_difficulty.get(difficulty)
        metrics_b = results_b.by_difficulty.get(difficulty)

        if metrics_a and metrics_b:
            comparison["by_difficulty"][difficulty] = {
                "f1_diff": metrics_a.f1 - metrics_b.f1,
                "engine_a_f1": metrics_a.f1,
                "engine_b_f1": metrics_b.f1,
            }

    # Compare by language
    for language in set(results_a.by_language.keys()) | set(results_b.by_language.keys()):
        metrics_a = results_a.by_language.get(language)
        metrics_b = results_b.by_language.get(language)

        if metrics_a and metrics_b:
            comparison["by_language"][language] = {
                "f1_diff": metrics_a.f1 - metrics_b.f1,
                "engine_a_f1": metrics_a.f1,
                "engine_b_f1": metrics_b.f1,
            }

    return comparison