"""Stratified evaluation matrix.

This is the sales weapon: explicit performance breakdown by:
- Clone type (Type I/II/III/IV)
- Difficulty (EASY/MEDIUM/HARD/EXPERT)
- Language (python/java/etc.)

This becomes what competitors usually lack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.backend.benchmark.contracts.evaluation_result import (
    EnrichedPair,
    EvaluationResult,
)
from evaluation.core.metrics import compute_metrics


@dataclass
class StratifiedMetrics:
    """Metrics for a specific stratum (slice).

    Attributes:
        stratum_name: Name of this stratum (e.g., "type-1", "HARD").
        n_samples: Number of samples in this stratum.
        precision: Precision score.
        recall: Recall score.
        f1: F1 score.
        accuracy: Accuracy score.
        tp: True positives.
        fp: False positives.
        fn: False negatives.
        tn: True negatives.
    """

    stratum_name: str
    n_samples: int
    precision: float
    recall: float
    f1: float
    accuracy: float
    tp: int
    fp: int
    fn: int
    tn: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stratum_name": self.stratum_name,
            "n_samples": self.n_samples,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "accuracy": self.accuracy,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
        }


@dataclass
class StratifiedMatrix:
    """Complete stratified evaluation matrix.

    Attributes:
        engine_name: Name of the engine.
        by_clone_type: Metrics broken down by clone type.
        by_difficulty: Metrics broken down by difficulty.
        by_language: Metrics broken down by language.
        overall: Overall metrics.
    """

    engine_name: str
    by_clone_type: Dict[str, StratifiedMetrics] = field(default_factory=dict)
    by_difficulty: Dict[str, StratifiedMetrics] = field(default_factory=dict)
    by_language: Dict[str, StratifiedMetrics] = field(default_factory=dict)
    overall: Optional[StratifiedMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_name": self.engine_name,
            "overall": self.overall.to_dict() if self.overall else None,
            "by_clone_type": {k: v.to_dict() for k, v in self.by_clone_type.items()},
            "by_difficulty": {k: v.to_dict() for k, v in self.by_difficulty.items()},
            "by_language": {k: v.to_dict() for k, v in self.by_language.items()},
        }

    def summary_table(self) -> str:
        """Generate a summary table string."""
        lines = []
        lines.append(f"Engine: {self.engine_name}")
        lines.append("=" * 60)

        if self.overall:
            lines.append(
                f"Overall: P={self.overall.precision:.4f} R={self.overall.recall:.4f} F1={self.overall.f1:.4f}"
            )

        lines.append("\nBy Clone Type:")
        lines.append("-" * 40)
        for name, m in sorted(self.by_clone_type.items()):
            lines.append(
                f"  {name:12s}: P={m.precision:.4f} R={m.recall:.4f} F1={m.f1:.4f} (n={m.n_samples})"
            )

        lines.append("\nBy Difficulty:")
        lines.append("-" * 40)
        for name, m in sorted(self.by_difficulty.items()):
            lines.append(
                f"  {name:12s}: P={m.precision:.4f} R={m.recall:.4f} F1={m.f1:.4f} (n={m.n_samples})"
            )

        lines.append("\nBy Language:")
        lines.append("-" * 40)
        for name, m in sorted(self.by_language.items()):
            lines.append(
                f"  {name:12s}: P={m.precision:.4f} R={m.recall:.4f} F1={m.f1:.4f} (n={m.n_samples})"
            )

        return "\n".join(lines)


def _compute_stratum_metrics(
    results: List[EvaluationResult],
    pairs: List[EnrichedPair],
    threshold: float,
) -> StratifiedMetrics:
    """Compute metrics for a single stratum.

    Args:
        results: Evaluation results for this stratum.
        pairs: Enriched pairs for this stratum.
        threshold: Decision threshold.

    Returns:
        StratifiedMetrics for this stratum.
    """
    tp = fp = fn = tn = 0
    n_samples = len(results)

    for result, pair in zip(results, pairs):
        predicted = result.decision
        truth = pair.label == 1

        if predicted and truth:
            tp += 1
        elif predicted and not truth:
            fp += 1
        elif not predicted and truth:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    accuracy = (tp + tn) / n_samples if n_samples > 0 else 0.0

    return StratifiedMetrics(
        stratum_name="",
        n_samples=n_samples,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
    )


def compute_stratified_matrix(
    results: List[EvaluationResult],
    pairs: List[EnrichedPair],
    threshold: float = 0.5,
) -> StratifiedMatrix:
    """Compute stratified evaluation matrix.

    Args:
        results: List of evaluation results.
        pairs: List of enriched pairs (must match results order).
        threshold: Decision threshold.

    Returns:
        StratifiedMatrix with breakdowns by clone type, difficulty, language.
    """
    if len(results) != len(pairs):
        raise ValueError("results and pairs must have same length")

    engine_name = results[0].engine if results else "unknown"

    # Clone type names
    clone_type_names = {
        0: "non-clone",
        1: "type-1",
        2: "type-2",
        3: "type-3",
        4: "type-4",
    }

    # Group by clone type
    by_clone_type: Dict[str, Tuple[List[EvaluationResult], List[EnrichedPair]]] = {}
    for result, pair in zip(results, pairs):
        ct_name = clone_type_names.get(pair.clone_type, f"type-{pair.clone_type}")
        if ct_name not in by_clone_type:
            by_clone_type[ct_name] = ([], [])
        by_clone_type[ct_name][0].append(result)
        by_clone_type[ct_name][1].append(pair)

    # Group by difficulty
    by_difficulty: Dict[str, Tuple[List[EvaluationResult], List[EnrichedPair]]] = {}
    for result, pair in zip(results, pairs):
        diff = pair.difficulty
        if diff not in by_difficulty:
            by_difficulty[diff] = ([], [])
        by_difficulty[diff][0].append(result)
        by_difficulty[diff][1].append(pair)

    # Group by language
    by_language: Dict[str, Tuple[List[EvaluationResult], List[EnrichedPair]]] = {}
    for result, pair in zip(results, pairs):
        lang = pair.language
        if lang not in by_language:
            by_language[lang] = ([], [])
        by_language[lang][0].append(result)
        by_language[lang][1].append(pair)

    # Compute metrics for each stratum
    matrix = StratifiedMatrix(engine_name=engine_name)

    # Overall
    overall = _compute_stratum_metrics(results, pairs, threshold)
    overall.stratum_name = "overall"
    matrix.overall = overall

    # By clone type
    for name, (stratum_results, stratum_pairs) in by_clone_type.items():
        metrics = _compute_stratum_metrics(stratum_results, stratum_pairs, threshold)
        metrics.stratum_name = name
        matrix.by_clone_type[name] = metrics

    # By difficulty
    for name, (stratum_results, stratum_pairs) in by_difficulty.items():
        metrics = _compute_stratum_metrics(stratum_results, stratum_pairs, threshold)
        metrics.stratum_name = name
        matrix.by_difficulty[name] = metrics

    # By language
    for name, (stratum_results, stratum_pairs) in by_language.items():
        metrics = _compute_stratum_metrics(stratum_results, stratum_pairs, threshold)
        metrics.stratum_name = name
        matrix.by_language[name] = metrics

    return matrix
