"""Evaluation runner for cross-dataset benchmarking.

Computes Precision/Recall/F1, ROC-AUC, PR-AUC for tool predictions
against ground truth labels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class EvaluationResult:
    """Complete evaluation result for one tool on one dataset."""
    dataset_name: str
    tool_name: str
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    accuracy: float = 0.0
    roc_auc: float = 0.0
    pr_auc: float = 0.0
    threshold: float = 0.5
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    num_pairs: int = 0
    scores: List[float] = field(default_factory=list)
    labels: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset_name,
            "tool": self.tool_name,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "threshold": self.threshold,
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "num_pairs": self.num_pairs,
        }


class EvaluationRunner:
    """Runs evaluation and computes all metrics.

    Usage:
        runner = EvaluationRunner()
        result = runner.evaluate(dataset, tool, threshold=0.5)
    """

    def __init__(self, default_threshold: float = 0.5):
        self._default_threshold = default_threshold

    def evaluate(
        self,
        dataset,
        tool,
        threshold: Optional[float] = None,
        progress_fn=None,
    ) -> EvaluationResult:
        """Evaluate a tool on a dataset.

        Args:
            dataset: UnifiedBenchmarkDataset or any object with
                     pairs that have code_a, code_b, label attributes.
            tool: ToolAdapter with compare(code_a, code_b) -> float.
            threshold: Classification threshold (default 0.5).
            progress_fn: Optional callback(current, total).

        Returns:
            EvaluationResult with all metrics.
        """
        if threshold is None:
            threshold = self._default_threshold

        pairs = dataset.pairs
        scores = []
        labels = []

        for idx, pair in enumerate(pairs):
            code_a = getattr(pair, "code_a", "")
            code_b = getattr(pair, "code_b", "")
            label = int(getattr(pair, "label", 0))
            score = tool.compare(code_a, code_b)
            scores.append(score)
            labels.append(label)
            if progress_fn:
                progress_fn(idx + 1, len(pairs))

        return self.compute_metrics(
            dataset_name=dataset.name,
            tool_name=tool.name,
            scores=scores,
            labels=labels,
            threshold=threshold,
        )

    def compute_metrics(
        self,
        dataset_name: str,
        tool_name: str,
        scores: List[float],
        labels: List[int],
        threshold: float = 0.5,
    ) -> EvaluationResult:
        """Compute all metrics from scores and labels.

        Args:
            dataset_name: Name of the dataset.
            tool_name: Name of the tool.
            scores: Predicted similarity scores in [0, 1].
            labels: Ground truth labels (0 or 1).
            threshold: Classification threshold.

        Returns:
            EvaluationResult with all computed metrics.
        """
        y_true = np.array(labels, dtype=np.int32)
        y_score = np.array(scores, dtype=np.float64)
        y_pred = (y_score >= threshold).astype(np.int32)

        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        tn = int(np.sum((y_pred == 0) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))

        precision_val = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall_val = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_val = (
            2 * precision_val * recall_val / (precision_val + recall_val)
            if (precision_val + recall_val) > 0
            else 0.0
        )
        total = tp + tn + fp + fn
        accuracy_val = (tp + tn) / total if total > 0 else 0.0

        roc_auc_val = self._compute_roc_auc(y_true, y_score)
        pr_auc_val = self._compute_pr_auc(y_true, y_score)

        result = EvaluationResult(
            dataset_name=dataset_name,
            tool_name=tool_name,
            precision=precision_val,
            recall=recall_val,
            f1=f1_val,
            accuracy=accuracy_val,
            roc_auc=roc_auc_val,
            pr_auc=pr_auc_val,
            threshold=threshold,
            tp=tp,
            fp=fp,
            tn=tn,
            fn=fn,
            num_pairs=len(scores),
            scores=scores,
            labels=labels,
        )
        return result

    def find_optimal_threshold(
        self,
        scores: List[float],
        labels: List[int],
        strategy: str = "f1_max",
    ) -> Tuple[float, float]:
        """Find the optimal threshold.

        Args:
            scores: Predicted scores.
            labels: Ground truth labels.
            strategy: 'f1_max', 'precision_max', or 'recall_max'.

        Returns:
            (best_threshold, best_score).
        """
        y_true = np.array(labels, dtype=np.int32)
        y_score = np.array(scores, dtype=np.float64)

        best_threshold = 0.5
        best_score = 0.0

        for t_int in range(0, 101):
            t = t_int / 100.0
            y_pred = (y_score >= t).astype(np.int32)

            tp = int(np.sum((y_pred == 1) & (y_true == 1)))
            fp = int(np.sum((y_pred == 1) & (y_true == 0)))
            fn = int(np.sum((y_pred == 0) & (y_true == 1)))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            )

            if strategy == "f1_max":
                score = f1
            elif strategy == "precision_max":
                score = prec
            elif strategy == "recall_max":
                score = rec
            else:
                score = f1

            if score > best_score:
                best_score = score
                best_threshold = t

        return best_threshold, best_score

    def _compute_roc_auc(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
    ) -> float:
        try:
            from sklearn.metrics import roc_auc_score
            return float(roc_auc_score(y_true, y_score))
        except Exception:
            return self._compute_roc_auc_manual(y_true, y_score)

    def _compute_roc_auc_manual(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
    ) -> float:
        pos = np.sum(y_true == 1)
        neg = np.sum(y_true == 0)
        if pos == 0 or neg == 0:
            return 0.0

        desc_score_indices = np.argsort(-y_score)
        y_true_sorted = y_true[desc_score_indices]
        tps = np.cumsum(y_true_sorted)
        fps = np.cumsum(1 - y_true_sorted)

        tpr = tps / pos
        fpr = fps / neg

        tpr = np.concatenate([[0], tpr, [1]])
        fpr = np.concatenate([[0], fpr, [1]])

        return float(np.trapezoid(tpr, fpr))

    def _compute_pr_auc(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
    ) -> float:
        try:
            from sklearn.metrics import average_precision_score
            return float(average_precision_score(y_true, y_score))
        except Exception:
            return self._compute_pr_auc_manual(y_true, y_score)

    def _compute_pr_auc_manual(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
    ) -> float:
        desc_indices = np.argsort(-y_score)
        y_true_sorted = y_true[desc_indices]
        y_score_sorted = y_score[desc_indices]

        total_pos = np.sum(y_true)
        if total_pos == 0:
            return 0.0

        tp = 0
        fp = 0
        precisions = []
        recalls = []

        for i in range(len(y_true_sorted)):
            if y_true_sorted[i] == 1:
                tp += 1
            else:
                fp += 1
            precisions.append(tp / (tp + fp))
            recalls.append(tp / total_pos)

        recalls = np.array([0] + recalls)
        precisions = np.array([1] + precisions)

        recall_diff = np.diff(recalls)
        return float(np.sum(precisions[1:] * recall_diff))
