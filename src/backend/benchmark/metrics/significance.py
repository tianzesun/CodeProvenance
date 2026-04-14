"""Compatibility significance helpers for legacy benchmark tests."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class McNemarResult:
    """Result for McNemar's paired classification test."""

    statistic: float
    p_value: float
    is_significant: bool
    b: int
    c: int


@dataclass(frozen=True)
class EngineComparisonResult:
    """Summary of a two-engine statistical comparison."""

    metric_name: str
    engine_a_value: float
    engine_b_value: float
    p_value: float
    is_significant: bool
    ci_lower: float
    ci_upper: float


def bootstrap_confidence_interval(
    scores: Sequence[float],
    labels: Sequence[int],
    *,
    threshold: float = 0.5,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """Compute simple bootstrap confidence intervals for binary metrics."""
    if not scores or not labels:
        zero = {"value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
        return {"f1": dict(zero), "precision": dict(zero), "recall": dict(zero)}

    rng = random.Random(seed)
    paired = list(zip(scores, labels))
    predicted = [1 if score >= threshold else 0 for score in scores]
    point = _binary_metrics(predicted, labels)

    samples = {"precision": [], "recall": [], "f1": []}
    for _ in range(max(1, n_bootstrap)):
        batch = [paired[rng.randrange(len(paired))] for _ in range(len(paired))]
        boot_scores = [score for score, _ in batch]
        boot_labels = [label for _, label in batch]
        boot_predicted = [1 if score >= threshold else 0 for score in boot_scores]
        metrics = _binary_metrics(boot_predicted, boot_labels)
        for name in samples:
            samples[name].append(metrics[name])

    result: Dict[str, Dict[str, float]] = {}
    for name, values in samples.items():
        values.sort()
        lower_index = int(0.025 * (len(values) - 1))
        upper_index = int(0.975 * (len(values) - 1))
        result[name] = {
            "value": point[name],
            "ci_lower": values[lower_index],
            "ci_upper": values[upper_index],
        }
    return result


def mcnemar_test(
    labels: Sequence[int],
    pred_a: Sequence[int],
    pred_b: Sequence[int],
) -> McNemarResult:
    """Run a lightweight exact McNemar test."""
    correct_a = [int(a == label) for a, label in zip(pred_a, labels)]
    correct_b = [int(b == label) for b, label in zip(pred_b, labels)]

    b = sum(1 for a_ok, b_ok in zip(correct_a, correct_b) if a_ok and not b_ok)
    c = sum(1 for a_ok, b_ok in zip(correct_a, correct_b) if not a_ok and b_ok)

    if b + c == 0:
        return McNemarResult(statistic=0.0, p_value=1.0, is_significant=False, b=0, c=0)

    statistic = ((abs(b - c) - 1) ** 2) / (b + c)
    p_value = _exact_mcnemar_p_value(b, c)
    return McNemarResult(
        statistic=statistic,
        p_value=p_value,
        is_significant=p_value < 0.05,
        b=b,
        c=c,
    )


def compare_engines(
    scores_a: Sequence[float],
    scores_b: Sequence[float],
    labels: Sequence[int],
    *,
    metric_name: str = "f1",
    threshold: float = 0.5,
) -> EngineComparisonResult:
    """Compare two engines using F1 plus McNemar significance."""
    pred_a = [1 if score >= threshold else 0 for score in scores_a]
    pred_b = [1 if score >= threshold else 0 for score in scores_b]
    metrics_a = _binary_metrics(pred_a, labels)
    metrics_b = _binary_metrics(pred_b, labels)
    mcnemar = mcnemar_test(labels, pred_a, pred_b)

    diff = metrics_a[metric_name] - metrics_b[metric_name]
    margin = abs(diff)
    return EngineComparisonResult(
        metric_name=metric_name,
        engine_a_value=metrics_a[metric_name],
        engine_b_value=metrics_b[metric_name],
        p_value=mcnemar.p_value,
        is_significant=mcnemar.is_significant,
        ci_lower=diff - margin,
        ci_upper=diff + margin,
    )


def add_significance_to_results(
    scores: Sequence[float],
    labels: Sequence[int],
    *,
    threshold: float = 0.5,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Attach confidence intervals to benchmark results."""
    return bootstrap_confidence_interval(
        scores,
        labels,
        threshold=threshold,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )


def _binary_metrics(predicted: Sequence[int], labels: Sequence[int]) -> Dict[str, float]:
    tp = sum(1 for pred, label in zip(predicted, labels) if pred == 1 and label == 1)
    fp = sum(1 for pred, label in zip(predicted, labels) if pred == 1 and label == 0)
    fn = sum(1 for pred, label in zip(predicted, labels) if pred == 0 and label == 1)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _exact_mcnemar_p_value(b: int, c: int) -> float:
    n = b + c
    k = min(b, c)
    if n == 0:
        return 1.0

    tail = 0.0
    for value in range(0, k + 1):
        tail += math.comb(n, value) * (0.5 ** n)
    return min(1.0, 2 * tail)
