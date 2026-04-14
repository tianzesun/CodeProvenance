"""Evaluator - Metrics computation with canonical schema support.

This module computes evaluation metrics (precision, recall, F1, ROC-AUC, calibration)
based on scores provided by the fusion engine. It does NOT compute similarity scores.

Responsibility: Metrics computation, statistical analysis, performance evaluation
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import numpy as np


@dataclass
class EvaluationResult:
    """Result of evaluation metrics computation."""
    precision: float
    recall: float
    f1: float
    accuracy: float
    auc_roc: Optional[float] = None
    ece: Optional[float] = None
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class Evaluator:
    """Production-safe evaluator for computing metrics.
    
    This evaluator does NOT compute similarity scores.
    It only computes metrics based on scores provided by the fusion engine.
    """
    
    def __init__(self, threshold: float = 0.5):
        """Initialize evaluator with decision threshold.
        
        Args:
            threshold: Threshold for converting similarity scores to binary decisions
        """
        self.threshold = threshold
    
    def evaluate(
        self,
        predictions: List[Dict[str, Any]],
        label_map: Dict[tuple, int],
        threshold: Optional[float] = None
    ) -> EvaluationResult:
        """Compute evaluation metrics.
        
        Args:
            predictions: List of prediction dicts with 'similarity' score and file pairs
            label_map: Mapping from (file1, file2) tuples to ground truth labels (0 or 1)
            threshold: Optional override for decision threshold
            
        Returns:
            EvaluationResult with computed metrics
        """
        effective_threshold = threshold if threshold is not None else self.threshold
        
        tp = fp = fn = tn = 0
        all_scores = []
        all_labels = []
        
        for pred in predictions:
            # Get similarity score (already computed by fusion engine)
            score = pred.get("similarity", 0.0)
            
            # Get file pair
            file1 = pred.get("file1", "")
            file2 = pred.get("file2", "")
            pair_key = tuple(sorted([file1, file2]))
            
            # Convert score to binary prediction using threshold
            predicted = 1 if score >= effective_threshold else 0
            
            # Get ground truth
            truth = label_map.get(pair_key, -1)
            if truth < 0:
                continue  # Skip pairs without ground truth
            
            all_scores.append(score)
            all_labels.append(truth)
            
            # Update confusion matrix
            if predicted == 1 and truth == 1:
                tp += 1
            elif predicted == 1 and truth == 0:
                fp += 1
            elif predicted == 0 and truth == 1:
                fn += 1
            else:
                tn += 1
        
        # Compute metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
        
        # Compute ROC-AUC
        auc_roc = self._compute_auc_roc(all_scores, all_labels)
        
        # Compute ECE
        ece = self._compute_ece(all_scores, all_labels)
        
        return EvaluationResult(
            precision=precision,
            recall=recall,
            f1=f1,
            accuracy=accuracy,
            auc_roc=auc_roc,
            ece=ece,
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            metadata={
                "threshold": effective_threshold,
                "num_pairs": len(predictions),
                "num_labeled": tp + fp + fn + tn,
            }
        )
    
    def compute_metrics_from_scores(
        self,
        scores: List[float],
        labels: List[int],
        threshold: Optional[float] = None
    ) -> EvaluationResult:
        """Compute metrics directly from scores and labels.
        
        Args:
            scores: List of similarity scores (computed by fusion engine)
            labels: List of ground truth labels (0 or 1)
            threshold: Optional override for decision threshold
            
        Returns:
            EvaluationResult with computed metrics
        """
        effective_threshold = threshold if threshold is not None else self.threshold
        
        if len(scores) != len(labels):
            raise ValueError("Scores and labels must have same length")
        
        tp = fp = fn = tn = 0
        
        for score, truth in zip(scores, labels):
            predicted = 1 if score >= effective_threshold else 0
            
            if predicted == 1 and truth == 1:
                tp += 1
            elif predicted == 1 and truth == 0:
                fp += 1
            elif predicted == 0 and truth == 1:
                fn += 1
            else:
                tn += 1
        
        # Compute metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
        
        # Compute ROC-AUC
        auc_roc = self._compute_auc_roc(scores, labels)
        
        # Compute ECE
        ece = self._compute_ece(scores, labels)
        
        return EvaluationResult(
            precision=precision,
            recall=recall,
            f1=f1,
            accuracy=accuracy,
            auc_roc=auc_roc,
            ece=ece,
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            metadata={
                "threshold": effective_threshold,
                "num_pairs": len(scores),
            }
        )
    
    def _compute_auc_roc(self, scores: List[float], labels: List[int]) -> Optional[float]:
        """Compute Area Under ROC Curve.
        
        Args:
            scores: Similarity scores.
            labels: Ground truth labels (0 or 1).
            
        Returns:
            AUC-ROC score, or None if computation fails.
        """
        if len(scores) < 2:
            return None
        
        # Check if we have both classes
        unique_labels = set(labels)
        if len(unique_labels) < 2:
            return None
        
        # Sort by score descending
        sorted_indices = np.argsort(scores)[::-1]
        sorted_labels = [labels[i] for i in sorted_indices]
        
        # Compute TPR and FPR at each threshold
        n_pos = sum(1 for l in labels if l == 1)
        n_neg = sum(1 for l in labels if l == 0)
        
        if n_pos == 0 or n_neg == 0:
            return None
        
        tp = 0
        fp = 0
        tpr_list = [0.0]
        fpr_list = [0.0]
        
        for label in sorted_labels:
            if label == 1:
                tp += 1
            else:
                fp += 1
            tpr_list.append(tp / n_pos)
            fpr_list.append(fp / n_neg)
        
        # Compute AUC using trapezoidal rule
        auc = 0.0
        for i in range(1, len(fpr_list)):
            auc += (fpr_list[i] - fpr_list[i - 1]) * (tpr_list[i] + tpr_list[i - 1]) / 2
        
        return float(auc)
    
    def _compute_ece(
        self,
        scores: List[float],
        labels: List[int],
        n_bins: int = 10,
    ) -> Optional[float]:
        """Compute Expected Calibration Error.
        
        Args:
            scores: Similarity scores.
            labels: Ground truth labels (0 or 1).
            n_bins: Number of bins for calibration.
            
        Returns:
            ECE score, or None if computation fails.
        """
        if len(scores) < n_bins:
            return None
        
        scores_arr = np.array(scores)
        labels_arr = np.array(labels)
        
        # Create bins
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(scores_arr, bin_edges) - 1
        bin_indices = np.clip(bin_indices, 0, n_bins - 1)
        
        ece = 0.0
        
        for bin_idx in range(n_bins):
            mask = bin_indices == bin_idx
            n_in_bin = mask.sum()
            
            if n_in_bin == 0:
                continue
            
            bin_confidences = scores_arr[mask]
            bin_labels = labels_arr[mask]
            
            mean_confidence = float(bin_confidences.mean())
            mean_accuracy = float(bin_labels.mean())
            gap = abs(mean_confidence - mean_accuracy)
            
            # Weight by bin size
            weight = n_in_bin / len(scores)
            ece += weight * gap
        
        return float(ece)
