"""
A/B Testing Framework for Code Similarity Detection.

Compares multiple detection methods (baseline, TF-IDF, AST, hybrid) on
the same test set to measure relative performance.

Supports:
- Side-by-side metric comparison
- Statistical significance testing
- Performance-by-obfuscation-level analysis
- Confusion matrix generation
"""
from typing import Dict, List, Any, Optional, Tuple, Callable
from pathlib import Path
import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ABTestResult:
    """Result for a single method in an A/B test."""
    method_name: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    tp: int
    fp: int
    fn: int
    tn: int
    execution_time_ms: float
    auc_roc: float = 0.0
    confusion_matrix: List[List[int]] = field(default_factory=list)


@dataclass
class ABTestReport:
    """Complete A/B test report."""
    experiment_name: str
    timestamp: str
    dataset: str
    num_pairs: int
    results: Dict[str, ABTestResult] = field(default_factory=dict)
    best_method: str = ""
    best_metric: str = "f1"
    statistical_significance: Dict[str, Dict[str, float]] = field(default_factory=dict)
    obfuscation_level_results: Dict[str, Dict[str, Dict[str, float]]] = field(default_factory=dict)


@dataclass
class TestPair:
    """A single test pair for evaluation."""
    code1: str
    code2: str
    label: int  # 1 = similar/clone, 0 = different
    obfuscation_level: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ABTester:
    """
    A/B Testing framework for comparing similarity detection methods.

    Usage:
        tester = ABTester(experiment_name="compare_methods")
        tester.add_method("tfidf", tfidf_scoring_fn)
        tester.add_method("ast", ast_scoring_fn)
        tester.load_test_pairs(pairs)
        report = tester.run()
    """

    def __init__(self, experiment_name: str = "ab_test",
                 output_dir: Path = Path("benchmark/reports")):
        self.experiment_name = experiment_name
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.methods: Dict[str, Callable[[str, str], float]] = {}
        self.test_pairs: List[TestPair] = []
        self._results_cache: Optional[ABTestReport] = None

    def add_method(self, name: str, scoring_fn: Callable[[str, str], float]) -> None:
        """
        Add a detection method for comparison.

        Args:
            name: Method identifier
            scoring_fn: Function that takes (code1, code2) and returns similarity [0, 1]
        """
        self.methods[name] = scoring_fn

    def add_test_pair(self, pair: TestPair) -> None:
        """Add a test pair with ground truth label."""
        self.test_pairs.append(pair)

    def load_test_pairs(self, pairs: List[TestPair]) -> None:
        """Load test pairs from list."""
        self.test_pairs = pairs

    def load_from_predictions_and_ground_truth(
        self,
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        code_store: Dict[str, str] = None
    ) -> None:
        """
        Load test pairs from prediction/ground truth format.

        Args:
            predictions: List of {"file1": ..., "file2": ..., "similarity": ...}
            ground_truth: {"pairs": [{"file1": ..., "file2": ..., "label": 0|1}]}
            code_store: Optional map of filename -> source code
        """
        import random
        truth_map = {}
        for gt in ground_truth.get("pairs", []):
            key = tuple(sorted([gt["file1"], gt["file2"]]))
            truth_map[key] = gt.get("label", 0)

        pred_map = {}
        for pred in predictions:
            key = tuple(sorted([pred["file1"], pred["file2"]]))
            pred_map[key] = pred.get("similarity", 0)

        # Create pairs
        all_keys = set(list(truth_map.keys()) + list(pred_map.keys()))
        for key in all_keys:
            label = truth_map.get(key, 0)
            code1 = code_store.get(key[0], "") if code_store else ""
            code2 = code_store.get(key[1], "") if code_store else ""
            
            self.test_pairs.append(TestPair(
                code1=code1,
                code2=code2,
                label=label,
                obfuscation_level=0,
            ))

    def run(self, threshold: float = 0.5,
            num_bootstrap: int = 1000) -> ABTestReport:
        """
        Run A/B test on all methods.

        Args:
            threshold: Similarity threshold for binary classification
            num_bootstrap: Number of bootstrap samples for significance testing

        Returns:
            ABTestReport with all results
        """
        report = ABTestReport(
            experiment_name=self.experiment_name,
            timestamp=datetime.now().isoformat(),
            dataset="unknown",
            num_pairs=len(self.test_pairs),
        )

        import time

        for name, scoring_fn in self.methods.items():
            start = time.time()
            
            # Score all pairs
            scored_pairs = []
            for pair in self.test_pairs:
                if pair.code1 and pair.code2:
                    score = scoring_fn(pair.code1, pair.code2)
                    scored_pairs.append((score, pair.label, pair.obfuscation_level))
                else:
                    scored_pairs.append((0.0, pair.label, pair.obfuscation_level))

            exec_time = (time.time() - start) * 1000

            # Compute metrics
            result = self._compute_metrics(scored_pairs, threshold, exec_time)
            result.method_name = name
            report.results[name] = result

        # Find best method
        if report.results:
            report.best_method = max(
                report.results.keys(),
                key=lambda n: getattr(report.results[n], report.best_metric, 0)
            )

        # Statistical significance
        report.statistical_significance = self._compute_significance(threshold, num_bootstrap)

        # Per-obfuscation-level results
        report.obfuscation_level_results = self._compute_by_obfuscation(threshold)

        self._results_cache = report
        return report

    def _compute_metrics(self, scored_pairs: List[Tuple[float, int, int]],
                         threshold: float, exec_time: float) -> ABTestResult:
        """Compute classification metrics from scored pairs."""
        tp = fp = fn = tn = 0

        for score, label, _ in scored_pairs:
            predicted = 1 if score >= threshold else 0
            if label == 1 and predicted == 1:
                tp += 1
            elif label == 0 and predicted == 1:
                fp += 1
            elif label == 1 and predicted == 0:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) else 0.0

        # AUC-ROC
        auc_roc = self._compute_auc_roc(scored_pairs)

        return ABTestResult(
            method_name="",
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            accuracy=round(accuracy, 4),
            tp=tp, fp=fp, fn=fn, tn=tn,
            execution_time_ms=round(exec_time, 2),
            auc_roc=round(auc_roc, 4),
            confusion_matrix=[[tp, fn], [fp, tn]],
        )

    def _compute_auc_roc(self, scored_pairs: List[Tuple[float, int, int]]) -> float:
        """Compute AUC-ROC from scored pairs."""
        pos_scores = [s for s, l, _ in scored_pairs if l == 1]
        neg_scores = [s for s, l, _ in scored_pairs if l == 0]

        if not pos_scores or not neg_scores:
            return 0.5

        concordant = 0
        ties = 0
        total = len(pos_scores) * len(neg_scores)

        for p in pos_scores:
            for n in neg_scores:
                if p > n:
                    concordant += 1
                elif p == n:
                    ties += 0.5

        return (concordant + ties) / total

    def _compute_significance(self, threshold: float,
                              num_bootstrap: int) -> Dict[str, Dict[str, float]]:
        """
        Compute statistical significance using bootstrap resampling.

        Returns dict method_pair -> {"f1_diff": ..., "p_value": ...}
        """
        if len(self.test_pairs) < 10:
            return {}

        import random

        method_names = list(self.methods.keys())
        significance = {}

        for i in range(len(method_names)):
            for j in range(i + 1, len(method_names)):
                m1, m2 = method_names[i], method_names[j]
                key = f"{m1}_vs_{m2}"

                f1_diffs = []
                for _ in range(num_bootstrap):
                    indices = [random.randint(0, len(self.test_pairs) - 1)
                               for _ in range(len(self.test_pairs))]
                    sample = [self.test_pairs[idx] for idx in indices]

                    # Score with both methods
                    scores1 = [self.methods[m1](p.code1, p.code2) for p in sample]
                    scores2 = [self.methods[m2](p.code1, p.code2) for p in sample]
                    labels = [p.label for p in sample]

                    f1_1 = self._compute_f1_from_scores(scores1, labels, threshold)
                    f1_2 = self._compute_f1_from_scores(scores2, labels, threshold)
                    f1_diffs.append(f1_1 - f1_2)

                mean_diff = statistics.mean(f1_diffs)
                std_diff = statistics.stdev(f1_diffs) if len(f1_diffs) > 1 else 1
                z_score = mean_diff / std_diff if std_diff > 0 else 0

                # Approximate p-value from z-score
                p_value = 2 * (1 - self._normal_cdf(abs(z_score)))

                significance[key] = {
                    "f1_diff": round(mean_diff, 4),
                    "z_score": round(z_score, 4),
                    "p_value": round(p_value, 4),
                    "significant": p_value < 0.05,
                }

        return significance

    def _compute_f1_from_scores(self, scores: List[float],
                                labels: List[int], threshold: float) -> float:
        """Compute F1 from scores and labels."""
        tp = fp = fn = 0
        for s, l in zip(scores, labels):
            pred = 1 if s >= threshold else 0
            if l == 1 and pred == 1:
                tp += 1
            elif l == 0 and pred == 1:
                fp += 1
            elif l == 1 and pred == 0:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    def _compute_by_obfuscation(self, threshold: float) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Compute metrics by obfuscation level."""
        level_groups: Dict[int, List[Tuple[str, float, int, int]]] = {}

        for name, scoring_fn in self.methods.items():
            for pair in self.test_pairs:
                level = pair.obfuscation_level
                score = scoring_fn(pair.code1, pair.code2) if pair.code1 and pair.code2 else 0.0
                level_groups.setdefault(level, []).append((name, score, pair.label, level))

        results = {}
        for level, items in level_groups.items():
            level_key = f"level_{level}"
            results[level_key] = {}
            by_method: Dict[str, List[Tuple[float, int, int]]] = {}
            for name, score, label, _ in items:
                by_method.setdefault(name, []).append((score, label, level))

            for name, scored in by_method.items():
                metrics = self._compute_metrics(scored, threshold, 0)
                results[level_key][name] = {
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                }

        return results

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def save_report(self, report: ABTestReport, format: str = "json") -> Path:
        """Save report to file."""
        data = {
            "experiment_name": report.experiment_name,
            "timestamp": report.timestamp,
            "dataset": report.dataset,
            "num_pairs": report.num_pairs,
            "best_method": report.best_method,
            "results": {},
            "statistical_significance": report.statistical_significance,
            "obfuscation_level_results": report.obfuscation_level_results,
        }

        for name, r in report.results.items():
            data["results"][name] = {
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "accuracy": r.accuracy,
                "auc_roc": r.auc_roc,
                "tp": r.tp,
                "fp": r.fp,
                "fn": r.fn,
                "tn": r.tn,
                "execution_time_ms": r.execution_time_ms,
                "confusion_matrix": r.confusion_matrix,
            }

        output_path = self.output_dir / f"{report.experiment_name}.{format}"
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        return output_path

    def print_comparison_table(self, report: ABTestReport) -> str:
        """Generate a comparison table as text."""
        lines = [
            f"\n{'='*80}",
            f"A/B Test Report: {report.experiment_name}",
            f"Pairs evaluated: {report.num_pairs}",
            f"Best method: {report.best_method}",
            f"{'='*80}\n",
            f"{'Method':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Accuracy':>10} {'AUC-ROC':>10}",
            f"{'-'*80}",
        ]

        for name, r in sorted(report.results.items(),
                              key=lambda x: x[1].f1, reverse=True):
            marker = " <-- Best" if name == report.best_method else ""
            lines.append(
                f"{name:<20} {r.precision:>10.4f} {r.recall:>10.4f} "
                f"{r.f1:>10.4f} {r.accuracy:>10.4f} {r.auc_roc:>10.4f}{marker}"
            )

        lines.append(f"{'='*80}")

        # Print statistical significance
        if report.statistical_significance:
            lines.append("\nStatistical Significance (F1 difference):")
            lines.append(f"{'Comparison':<30} {'F1 Diff':>10} {'p-value':>10} {'Significant':>12}")
            lines.append("-" * 70)
            for key, sig in report.statistical_significance.items():
                sig_marker = "Yes" if sig["significant"] else "No"
                lines.append(
                    f"{key:<30} {sig['f1_diff']:>10.4f} {sig['p_value']:>10.4f} {sig_marker:>12}"
                )

        return "\n".join(lines)