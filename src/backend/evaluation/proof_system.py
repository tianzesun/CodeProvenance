"""Accuracy proof system for professor-facing plagiarism review.

The proof system evaluates whether ranked cases are worth instructor time. It
therefore emphasizes Precision@10, Precision@20, NDCG@20, fixed-FPR recall,
hard-negative false positives, starter-code false-positive reduction, same-bug
recall, previous-term recall, ablations, and release gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


HARD_NEGATIVE_TYPES = {
    "starter_code_false_positive",
    "common_solution_false_positive",
    "standard_solution",
    "shared_library_usage",
}


@dataclass(frozen=True)
class ProofCase:
    """One labeled pair for release-readiness evaluation."""

    case_id: str
    score: float
    label: int
    category: str
    metadata: Dict[str, float | str | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ReleaseGate:
    """A named metric threshold required before production release."""

    metric: str
    minimum: Optional[float] = None
    maximum: Optional[float] = None

    def evaluate(self, metrics: Mapping[str, float]) -> bool:
        """Return whether a metric snapshot passes this gate."""
        value = float(metrics.get(self.metric, 0.0))
        if self.minimum is not None and value < self.minimum:
            return False
        if self.maximum is not None and value > self.maximum:
            return False
        return True


@dataclass(frozen=True)
class GateResult:
    """Release gate evaluation result."""

    metric: str
    value: float
    passed: bool
    threshold: str


@dataclass(frozen=True)
class ProofReport:
    """Complete proof report for release readiness."""

    metrics: Dict[str, float]
    gate_results: List[GateResult]
    release_ready: bool
    ablations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    tool_comparison: Dict[str, Dict[str, float]] = field(default_factory=dict)


DEFAULT_RELEASE_GATES = [
    ReleaseGate("precision_at_10", minimum=0.90),
    ReleaseGate("precision_at_20", minimum=0.85),
    ReleaseGate("hard_negative_false_positive_rate", maximum=0.03),
    ReleaseGate("starter_code_false_positive_reduction", minimum=0.70),
    ReleaseGate("same_bug_recall", minimum=0.85),
    ReleaseGate("previous_term_recall", minimum=0.90),
    ReleaseGate("embedding_only_high_risk_count", maximum=0.0),
]


class AccuracyProofSystem:
    """Compute professor-workflow proof metrics and release gates."""

    def evaluate(
        self,
        cases: Sequence[ProofCase],
        *,
        baseline_cases: Optional[Sequence[ProofCase]] = None,
        gates: Sequence[ReleaseGate] = DEFAULT_RELEASE_GATES,
        high_risk_threshold: float = 0.75,
        fixed_fpr: float = 0.01,
    ) -> ProofReport:
        """Evaluate a ranked output set against release-readiness gates."""
        metrics = self.metrics(
            cases,
            baseline_cases=baseline_cases,
            high_risk_threshold=high_risk_threshold,
            fixed_fpr=fixed_fpr,
        )
        gate_results = [self._evaluate_gate(gate, metrics) for gate in gates]
        return ProofReport(
            metrics=metrics,
            gate_results=gate_results,
            release_ready=all(result.passed for result in gate_results),
        )

    def metrics(
        self,
        cases: Sequence[ProofCase],
        *,
        baseline_cases: Optional[Sequence[ProofCase]] = None,
        high_risk_threshold: float = 0.75,
        fixed_fpr: float = 0.01,
    ) -> Dict[str, float]:
        """Compute all release proof metrics."""
        ordered = _sorted_cases(cases)
        metrics = {
            "precision_at_10": precision_at_k(ordered, 10),
            "precision_at_20": precision_at_k(ordered, 20),
            "ndcg_at_20": ndcg_at_k(ordered, 20),
            "recall_at_fixed_false_positive_rate": recall_at_fixed_fpr(
                ordered, fixed_fpr
            ),
            "hard_negative_false_positive_rate": category_false_positive_rate(
                ordered, HARD_NEGATIVE_TYPES, high_risk_threshold
            ),
            "same_bug_recall": category_recall(
                ordered, {"same_bug"}, high_risk_threshold
            ),
            "previous_term_recall": category_recall(
                ordered, {"previous_semester_reuse"}, high_risk_threshold
            ),
            "embedding_only_high_risk_count": float(
                embedding_only_high_risk_count(ordered, high_risk_threshold)
            ),
        }
        metrics["starter_code_false_positive_reduction"] = (
            starter_code_false_positive_reduction(
                baseline_cases or [], ordered, high_risk_threshold
            )
        )
        return {key: round(value, 4) for key, value in metrics.items()}

    def run_ablations(
        self,
        variants: Mapping[str, Sequence[ProofCase]],
        *,
        baseline_cases: Optional[Sequence[ProofCase]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Evaluate Layer A/B/C/D/E and guardrail variants side by side."""
        return {
            name: self.metrics(cases, baseline_cases=baseline_cases)
            for name, cases in variants.items()
        }

    def compare_tools(
        self,
        tool_outputs: Mapping[str, Sequence[ProofCase]],
    ) -> Dict[str, Dict[str, float]]:
        """Compare MOSS/JPlag/Dolos/IntegrityDesk using professor metrics."""
        return {tool: self.metrics(cases) for tool, cases in tool_outputs.items()}

    def _evaluate_gate(
        self, gate: ReleaseGate, metrics: Mapping[str, float]
    ) -> GateResult:
        value = float(metrics.get(gate.metric, 0.0))
        if gate.minimum is not None:
            threshold = f">= {gate.minimum}"
        else:
            threshold = f"<= {gate.maximum}"
        return GateResult(
            metric=gate.metric,
            value=round(value, 4),
            passed=gate.evaluate(metrics),
            threshold=threshold,
        )


def precision_at_k(cases: Sequence[ProofCase], k: int) -> float:
    """Return precision among the top-k ranked cases."""
    top = list(cases[:k])
    if not top:
        return 0.0
    return sum(case.label for case in top) / len(top)


def ndcg_at_k(cases: Sequence[ProofCase], k: int) -> float:
    """Return NDCG@k for binary or graded labels."""
    import math

    top = list(cases[:k])
    dcg = sum(
        (2**case.label - 1) / math.log2(index + 2) for index, case in enumerate(top)
    )
    ideal = sorted(cases, key=lambda case: case.label, reverse=True)[:k]
    idcg = sum(
        (2**case.label - 1) / math.log2(index + 2) for index, case in enumerate(ideal)
    )
    return dcg / idcg if idcg > 0 else 0.0


def recall_at_fixed_fpr(cases: Sequence[ProofCase], fixed_fpr: float) -> float:
    """Return maximum recall available without exceeding a fixed FPR."""
    positives = [case for case in cases if case.label == 1]
    negatives = [case for case in cases if case.label == 0]
    if not positives:
        return 0.0
    if not negatives:
        return 1.0

    best_recall = 0.0
    thresholds = sorted({case.score for case in cases}, reverse=True)
    for threshold in thresholds:
        tp = sum(1 for case in positives if case.score >= threshold)
        fp = sum(1 for case in negatives if case.score >= threshold)
        fpr = fp / len(negatives)
        if fpr <= fixed_fpr:
            best_recall = max(best_recall, tp / len(positives))
    return best_recall


def category_false_positive_rate(
    cases: Sequence[ProofCase],
    categories: Iterable[str],
    threshold: float,
) -> float:
    """Return high-risk false-positive rate for selected hard-negative categories."""
    category_set = set(categories)
    relevant = [
        case for case in cases if case.category in category_set and case.label == 0
    ]
    if not relevant:
        return 0.0
    false_positives = sum(1 for case in relevant if case.score >= threshold)
    return false_positives / len(relevant)


def category_recall(
    cases: Sequence[ProofCase],
    categories: Iterable[str],
    threshold: float,
) -> float:
    """Return high-risk recall for selected positive evidence categories."""
    category_set = set(categories)
    relevant = [
        case for case in cases if case.category in category_set and case.label == 1
    ]
    if not relevant:
        return 1.0
    true_positives = sum(1 for case in relevant if case.score >= threshold)
    return true_positives / len(relevant)


def starter_code_false_positive_reduction(
    baseline_cases: Sequence[ProofCase],
    improved_cases: Sequence[ProofCase],
    threshold: float,
) -> float:
    """Return relative reduction of starter-code false positives."""
    baseline_fpr = category_false_positive_rate(
        baseline_cases, {"starter_code_false_positive"}, threshold
    )
    improved_fpr = category_false_positive_rate(
        improved_cases, {"starter_code_false_positive"}, threshold
    )
    if baseline_fpr == 0:
        return 1.0 if improved_fpr == 0 else 0.0
    return max(0.0, (baseline_fpr - improved_fpr) / baseline_fpr)


def embedding_only_high_risk_count(cases: Sequence[ProofCase], threshold: float) -> int:
    """Count high-risk cases whose only strong evidence is embedding."""
    count = 0
    for case in cases:
        embedding_only = bool(case.metadata.get("embedding_only", False))
        if embedding_only and case.score >= threshold:
            count += 1
    return count


def _sorted_cases(cases: Sequence[ProofCase]) -> List[ProofCase]:
    """Sort cases by score descending with stable case-id tie break."""
    return sorted(cases, key=lambda case: (-case.score, case.case_id))
