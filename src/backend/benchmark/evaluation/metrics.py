"""Evaluation metrics for plagiarism detection.

Implements:
- Confusion matrix computation
- ROC/PR curves
- Precision, Recall, F1 at various thresholds
- Robustness scoring under adversarial transformations
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import numpy as np
from pathlib import Path


class GroundTruthLabel(Enum):
    """Ground truth labels for code pairs."""
    UNRELATED = 0       # Completely different code
    WEAK_SIMILARITY = 1  # Some similarity but not plagiarism
    SEMANTIC_CLONE = 2  # Same logic, different implementation
    EXACT_CLONE = 3     # Identical or near-identical code


@dataclass
class ConfusionMatrix:
    """Confusion matrix for binary classification."""
    tp: int = 0  # True Positive (correctly flagged plagiarism)
    fp: int = 0  # False Positive (incorrectly flagged)
    tn: int = 0  # True Negative (correctly not flagged)
    fn: int = 0  # False Negative (missed plagiarism)
    
    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)"""
        if self.tp + self.fp == 0:
            return 0.0
        return self.tp / (self.tp + self.fp)
    
    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)"""
        if self.tp + self.fn == 0:
            return 0.0
        return self.tp / (self.tp + self.fn)
    
    @property
    def f1(self) -> float:
        """F1 = 2 * P * R / (P + R)"""
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)
    
    @property
    def accuracy(self) -> float:
        """Accuracy = (TP + TN) / Total"""
        total = self.tp + self.fp + self.tn + self.fn
        if total == 0:
            return 0.0
        return (self.tp + self.tn) / total
    
    @property
    def false_positive_rate(self) -> float:
        """FPR = FP / (FP + TN)"""
        if self.fp + self.tn == 0:
            return 0.0
        return self.fp / (self.fp + self.tn)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "fpr": round(self.false_positive_rate, 4),
        }


@dataclass
class ThresholdResult:
    """Result at a specific threshold."""
    threshold: float
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    tn: int
    fn: int


@dataclass
class EvaluationMetrics:
    """Complete evaluation metrics for a detector."""
    tool_name: str
    dataset_name: str
    thresholds: List[ThresholdResult] = field(default_factory=list)
    confusion_matrix: Optional[ConfusionMatrix] = None
    best_threshold: Optional[float] = None
    best_f1: float = 0.0
    auc_roc: float = 0.0
    auc_pr: float = 0.0
    robustness_score: float = 0.0
    
    def compute_at_threshold(self, threshold: float, 
                            scores: List[float], 
                            labels: List[int]) -> ConfusionMatrix:
        """Compute confusion matrix at a given threshold."""
        cm = ConfusionMatrix()
        for score, label in zip(scores, labels):
            predicted = 1 if score >= threshold else 0
            if predicted == 1 and label == 1:
                cm.tp += 1
            elif predicted == 1 and label == 0:
                cm.fp += 1
            elif predicted == 0 and label == 0:
                cm.tn += 1
            elif predicted == 0 and label == 1:
                cm.fn += 1
        return cm
    
    def compute_roc_pr_curves(
        self,
        scores: List[float],
        labels: List[int],
    ) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Compute ROC and PR curve data points."""
        sorted_indices = np.argsort(scores)[::-1]
        sorted_scores = np.array(scores)[sorted_indices]
        sorted_labels = np.array(labels)[sorted_indices]
        
        # ROC curve: TPR vs FPR
        tpr_list = [0.0]
        fpr_list = [0.0]
        n_neg = int(np.sum(sorted_labels == 0))
        n_pos = int(np.sum(sorted_labels == 1))
        tp, fp = 0, 0
        
        for score, label in zip(sorted_scores, sorted_labels):
            if label == 1:
                tp += 1
            else:
                fp += 1
            tpr = tp / n_pos if n_pos > 0 else 0
            fpr = fp / n_neg if n_neg > 0 else 0
            tpr_list.append(tpr)
            fpr_list.append(fpr)
        
        # PR curve: Precision vs Recall
        precision_list = [0.0]
        recall_list = [0.0, 1.0]
        tp, fp = 0, 0
        
        for score, label in zip(sorted_scores, sorted_labels):
            if label == 1:
                tp += 1
            else:
                fp += 1
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / n_pos if n_pos > 0 else 0
            precision_list.append(precision)
            recall_list.append(recall)
        
        return tpr_list, fpr_list, precision_list, recall_list
    
    def compute_auc(self, x: List[float], y: List[float]) -> float:
        """Compute AUC using trapezoidal rule."""
        x, y = np.array(x), np.array(y)
        sorted_idx = np.argsort(x)
        x_sorted = x[sorted_idx]
        y_sorted = y[sorted_idx]
        return np.trapz(y_sorted, x_sorted)
    
    def evaluate(self, 
                scores: List[float], 
                labels: List[int],
                threshold: float = 0.5,
                compute_curves: bool = True) -> 'EvaluationMetrics':
        """Run full evaluation on scores and labels."""
        self.confusion_matrix = self.compute_at_threshold(threshold, scores, labels)
        self.best_threshold = threshold
        self.best_f1 = self.confusion_matrix.f1
        
        # Compute at multiple thresholds
        thresholds = np.linspace(0, 1, 21)
        for t in thresholds:
            cm = self.compute_at_threshold(t, scores, labels)
            self.thresholds.append(ThresholdResult(
                threshold=round(t, 2),
                precision=cm.precision,
                recall=cm.recall,
                f1=cm.f1,
                tp=cm.tp,
                fp=cm.fp,
                tn=cm.tn,
                fn=cm.fn
            ))
            if cm.f1 > self.best_f1:
                self.best_f1 = cm.f1
                self.best_threshold = t
        
        if compute_curves:
            tpr, fpr, prec, rec = self.compute_roc_pr_curves(scores, labels)
            self.auc_roc = self.compute_auc(fpr, tpr)
            self.auc_pr = self.compute_auc(rec, prec)
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool_name,
            "dataset": self.dataset_name,
            "best_threshold": round(self.best_threshold, 4) if self.best_threshold else None,
            "best_f1": round(self.best_f1, 4),
            "auc_roc": round(self.auc_roc, 4),
            "auc_pr": round(self.auc_pr, 4),
            "robustness": round(self.robustness_score, 4),
            "confusion_matrix": self.confusion_matrix.to_dict() if self.confusion_matrix else None,
        }


@dataclass
class RobustnessMetrics:
    """Metrics for adversarial robustness testing."""
    original_score: float
    transformed_scores: List[float]
    variance: float = 0.0
    mean_score: float = 0.0
    robustness_score: float = 0.0
    
    def compute(self) -> 'RobustnessMetrics':
        """Compute robustness metrics from transformed scores."""
        if not self.transformed_scores:
            return self
        
        self.mean_score = np.mean(self.transformed_scores)
        self.variance = np.var(self.transformed_scores)
        
        # Robustness = 1 - normalized variance
        # If score drops significantly under transformation, robustness is low
        if self.original_score > 0:
            score_drop = max(0, self.original_score - self.mean_score)
            self.robustness_score = 1 - (score_drop / self.original_score)
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_score": round(self.original_score, 4),
            "mean_transformed": round(self.mean_score, 4),
            "variance": round(self.variance, 4),
            "robustness_score": round(self.robustness_score, 4),
        }


class CodeTransformer:
    """Adversarial transformation pipeline for robustness testing."""
    
    @staticmethod
    def rename_variables(code: str, language: str) -> str:
        """Rename all variables to generic names."""
        import re
        # Simple placeholder - would need language-specific parsing
        # Replace common variable patterns
        result = code
        # This is a simplified version
        return result
    
    @staticmethod
    def reorder_blocks(code: str) -> str:
        """Reorder code blocks (functions, statements)."""
        # Would need AST parsing
        return code
    
    @staticmethod
    def add_comments(code: str) -> str:
        """Add noise comments."""
        lines = code.split('\n')
        noise_lines = ["# noise comment " + str(i) for i in range(3)]
        result = []
        for i, line in enumerate(lines):
            if i > 0 and i % 5 == 0:
                result.append(noise_lines[i % len(noise_lines)])
            result.append(line)
        return '\n'.join(result)
    
    @staticmethod
    def normalize_whitespace(code: str) -> str:
        """Normalize whitespace."""
        import re
        # Remove extra whitespace
        result = re.sub(r'\s+', ' ', code)
        return result.strip()


def compare_detectors(metrics_list: List[EvaluationMetrics]) -> Dict[str, Any]:
    """Compare multiple detector evaluations.
    
    Args:
        metrics_list: List of EvaluationMetrics for different tools
        
    Returns:
        Comparison summary with rankings
    """
    if not metrics_list:
        return {}
    
    # Rank by F1
    ranked = sorted(metrics_list, key=lambda m: m.best_f1, reverse=True)
    
    comparison = {
        "rankings": [],
        "best_by_f1": ranked[0].tool_name if ranked else None,
        "best_by_roc": max(metrics_list, key=lambda m: m.auc_roc).tool_name,
        "best_by_pr": max(metrics_list, key=lambda m: m.auc_pr).tool_name,
        "best_robustness": max(metrics_list, key=lambda m: m.robustness_score).tool_name,
    }
    
    for i, m in enumerate(ranked):
        comparison["rankings"].append({
            "rank": i + 1,
            "tool": m.tool_name,
            "f1": round(m.best_f1, 4),
            "auc_roc": round(m.auc_roc, 4),
            "auc_pr": round(m.auc_pr, 4),
            "robustness": round(m.robustness_score, 4),
        })
    
    return comparison
