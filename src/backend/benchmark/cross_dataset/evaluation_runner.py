"""Evaluation runner for cross-dataset benchmarking.

Computes:
    - Precision, Recall, F1 at optimal threshold
    - ROC-AUC
    - PR-AUC (Average Precision)
    - Additional statistics (accuracy, confusion matrix)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


@dataclass
class EvaluationResult:
    """Result of evaluating a tool on a dataset.

    Contains all computed metrics for one (tool, dataset) pair.
    """
    tool_name: str
    dataset_name: str
    num_pairs: int
    num_positive: int
    num_negative: int
    scores: List[float]
    labels: List[int]
    threshold: float
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float
    pr_auc: float
    tp: int
    fp: int
    tn: int
    fn: int
    optimal_threshold: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "dataset_name": self.dataset_name,
            "num_pairs": self.num_pairs,
            "num_positive": self.num_positive,
            "num_negative": self.num_negative,
            "threshold": self.threshold,
            "optimal_threshold": self.optimal_threshold,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
        }


class EvaluationRunner:
    """Runs evaluation on scored pairs and computes metrics.

    Usage:
        runner = EvaluationRunner()
        result = runner.evaluate(tool_name, dataset_name, scores, labels)
    """

    def __init__(self, threshold: float = 0.5, optimize_threshold: bool = True):
        """Initialize evaluation runner.

        Args:
            threshold: Default threshold for binary classification
            optimize_threshold: Whether to find optimal threshold via F1 maximization
        """
        self.default_threshold = threshold
        self.optimize_threshold = optimize_threshold

    def evaluate(
        self,
        tool_name: str,
        dataset_name: str,
        scores: List[float],
        labels: List[int],
        threshold: Optional[float] = None,
    ) -> EvaluationResult:
        """Evaluate tool performance on a dataset.

        Args:
            tool_name: Name of the tool being evaluated
            dataset_name: Name of the dataset
            scores: List of similarity scores [0, 1]
            labels: List of ground truth labels (0 or 1)
            threshold: Override threshold (uses default or optimal if None)

        Returns:
            EvaluationResult with all metrics
        """
        y_true = np.array(labels, dtype=int)
        y_scores = np.array(scores, dtype=float)

        num_pairs = len(y_true)
        num_positive = int(np.sum(y_true == 1))
        num_negative = int(np.sum(y_true == 0))

        optimal_threshold = self._find_optimal_threshold(y_true, y_scores)
        use_threshold = threshold if threshold is not None else (
            optimal_threshold if self.optimize_threshold else self.default_threshold
        )

        y_pred = (y_scores >= use_threshold).astype(int)

        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        tn = int(np.sum((y_pred == 0) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        acc = (tp + tn) / num_pairs if num_pairs > 0 else 0.0

        roc_auc = self._compute_roc_auc(y_true, y_scores)
        pr_auc = self._compute_pr_auc(y_true, y_scores)

        return EvaluationResult(
            tool_name=tool_name,
            dataset_name=dataset_name,
            num_pairs=num_pairs,
            num_positive=num_positive,
            num_negative=num_negative,
            scores=list(y_scores),
            labels=list(y_true),
            threshold=round(use_threshold, 4),
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1=round(f1, 4),
            accuracy=round(acc, 4),
            roc_auc=round(roc_auc, 4),
            pr_auc=round(pr_auc, 4),
            tp=tp,
            fp=fp,
            tn=tn,
            fn=fn,
            optimal_threshold=round(optimal_threshold, 4),
        )

    def evaluate_multiple(
        self,
        tool_name: str,
        dataset_name: str,
        scores_list: List[List[float]],
        labels: List[int],
        threshold: Optional[float] = None,
    ) -> List[EvaluationResult]:
        """Evaluate multiple score sets (e.g., from different runs) on same dataset.

        Args:
            tool_name: Name of the tool
            dataset_name: Name of the dataset
            scores_list: List of score lists (one per run)
            labels: Ground truth labels
            threshold: Optional threshold override

        Returns:
            List of EvaluationResult objects
        """
        results = []
        for i, scores in enumerate(scores_list):
            run_name = f"{tool_name}_run{i}"
            results.append(self.evaluate(run_name, dataset_name, scores, labels, threshold))
        return results

    @staticmethod
    def _find_optimal_threshold(
        y_true: np.ndarray,
        y_scores: np.ndarray,
    ) -> float:
        """Find threshold that maximizes F1 score.

        Args:
            y_true: Ground truth labels
            y_scores: Predicted scores

        Returns:
            Optimal threshold value
        """
        best_threshold = 0.5
        best_f1 = 0.0

        thresholds = np.unique(y_scores)
        if len(thresholds) > 101:
            thresholds = np.percentile(y_scores, np.linspace(0, 100, 101))

        for t in thresholds:
            y_pred = (y_scores >= t).astype(int)
            tp = np.sum((y_pred == 1) & (y_true == 1))
            fp = np.sum((y_pred == 1) & (y_true == 0))
            fn = np.sum((y_pred == 0) & (y_true == 1))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = t

        return float(best_threshold)

    @staticmethod
    def _compute_roc_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Compute ROC-AUC score.

        Args:
            y_true: Ground truth labels
            y_scores: Predicted scores

        Returns:
            ROC-AUC score
        """
        try:
            from sklearn.metrics import roc_auc_score
            return float(roc_auc_score(y_true, y_scores))
        except Exception:
            return EvaluationRunner._roc_auc_manual(y_true, y_scores)

    @staticmethod
    def _roc_auc_manual(y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Manual ROC-AUC computation using trapezoidal rule."""
        n_pos = np.sum(y_true == 1)
        n_neg = np.sum(y_true == 0)
        if n_pos == 0 or n_neg == 0:
            return 0.0

        sorted_indices = np.argsort(-y_scores)
        y_true_sorted = y_true[sorted_indices]

        tpr_list = [0.0]
        fpr_list = [0.0]
        tp = 0
        fp = 0

        for label in y_true_sorted:
            if label == 1:
                tp += 1
            else:
                fp += 1
            tpr_list.append(tp / n_pos)
            fpr_list.append(fp / n_neg)

        auc = 0.0
        for i in range(1, len(fpr_list)):
            auc += (fpr_list[i] - fpr_list[i - 1]) * (tpr_list[i] + tpr_list[i - 1]) / 2

        return float(auc)

    @staticmethod
    def _compute_pr_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Compute PR-AUC (Average Precision) score.

        Args:
            y_true: Ground truth labels
            y_scores: Predicted scores

        Returns:
            PR-AUC score
        """
        try:
            from sklearn.metrics import average_precision_score
            return float(average_precision_score(y_true, y_scores))
        except Exception:
            return EvaluationRunner._pr_auc_manual(y_true, y_scores)

    @staticmethod
    def _pr_auc_manual(y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Manual PR-AUC computation."""
        sorted_indices = np.argsort(-y_scores)
        y_true_sorted = y_true[sorted_indices]

        n_pos = np.sum(y_true == 1)
        if n_pos == 0:
            return 0.0

        precisions = []
        recalls = []
        tp = 0
        fp = 0

        for i, label in enumerate(y_true_sorted):
            if label == 1:
                tp += 1
            else:
                fp += 1
            precisions.append(tp / (tp + fp))
            recalls.append(tp / n_pos)

        if not precisions:
            return 0.0

        auc = 0.0
        for i in range(1, len(recalls)):
            auc += (recalls[i] - recalls[i - 1]) * (precisions[i] + precisions[i - 1]) / 2

        return float(auc)
