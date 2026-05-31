"""K-fold stratified cross-validation for benchmark evaluation.

Provides rigorous cross-validation protocol to prevent overfitting
and compute confidence intervals for all metrics.

Key features:
- Stratified k-fold to preserve class distribution
- Per-fold confusion matrices and metrics
- Aggregated CI and variance estimates
- Fold-stability analysis
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
from pathlib import Path

@dataclass
class FoldMetrics:
    """Metrics for a single fold.
    
    Attributes:
        fold_id: Fold index (0 to k-1).
        precision: Precision on this fold.
        recall: Recall on this fold.
        f1: F1 score on this fold.
        roc_auc: ROC AUC on this fold.
        pr_auc: PR AUC on this fold.
        tp: True positives.
        fp: False positives.
        tn: True negatives.
        fn: False negatives.
        n_samples: Number of samples in fold.
    """
    fold_id: int
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    tp: int
    fp: int
    tn: int
    fn: int
    n_samples: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fold_id": self.fold_id,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "confusion_matrix": {
                "tp": self.tp,
                "fp": self.fp,
                "tn": self.tn,
                "fn": self.fn,
            },
            "n_samples": self.n_samples,
        }

@dataclass
class CrossValidationResult:
    """Complete cross-validation results.
    
    Attributes:
        k: Number of folds.
        fold_results: Metrics for each fold.
        mean_precision: Mean precision across folds.
        std_precision: Standard deviation of precision.
        mean_recall: Mean recall across folds.
        std_recall: Standard deviation of recall.
        mean_f1: Mean F1 across folds.
        std_f1: Standard deviation of F1.
        ci_f1: 95% confidence interval for F1.
        ci_precision: 95% confidence interval for precision.
        ci_recall: 95% confidence interval for recall.
        fold_stability: Coefficient of variation for F1 (lower is better).
    """
    k: int
    fold_results: List[FoldMetrics] = field(default_factory=list)
    mean_precision: float = 0.0
    std_precision: float = 0.0
    mean_recall: float = 0.0
    std_recall: float = 0.0
    mean_f1: float = 0.0
    std_f1: float = 0.0
    ci_f1: Tuple[float, float] = (0.0, 0.0)
    ci_precision: Tuple[float, float] = (0.0, 0.0)
    ci_recall: Tuple[float, float] = (0.0, 0.0)
    fold_stability: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "k": self.k,
            "fold_results": [f.to_dict() for f in self.fold_results],
            "mean_f1": round(self.mean_f1, 4),
            "std_f1": round(self.std_f1, 4),
            "ci_f1": (round(self.ci_f1[0], 4), round(self.ci_f1[1], 4)),
            "mean_precision": round(self.mean_precision, 4),
            "std_precision": round(self.std_precision, 4),
            "ci_precision": (round(self.ci_precision[0], 4), round(self.ci_precision[1], 4)),
            "mean_recall": round(self.mean_recall, 4),
            "std_recall": round(self.std_recall, 4),
            "ci_recall": (round(self.ci_recall[0], 4), round(self.ci_recall[1], 4)),
            "fold_stability": round(self.fold_stability, 4),
        }

class StratifiedKFoldSplitter:
    """Generate stratified k-fold splits."""
    
    def __init__(self, k: int = 5, seed: int = 42):
        """Initialize splitter.
        
        Args:
            k: Number of folds.
            seed: Random seed for reproducibility.
        """
        self.k = k
        self.seed = seed
    
    def split(
        self, 
        n_samples: int, 
        labels: List[int],
    ) -> List[Tuple[List[int], List[int]]]:
        """Generate stratified k-fold splits.
        
        Args:
            n_samples: Total number of samples.
            labels: Class labels for stratification.
            
        Returns:
            List of (train_indices, test_indices) tuples.
        """
        rng = np.random.RandomState(self.seed)
        labels = np.array(labels)
        
        # Get unique classes and their indices
        unique_classes = np.unique(labels)
        class_indices = {c: np.where(labels == c)[0] for c in unique_classes}
        
        # Shuffle indices within each class
        for c in unique_classes:
            rng.shuffle(class_indices[c])
        
        # Distribute samples across folds
        fold_indices: List[List[int]] = [[] for _ in range(self.k)]
        for c in unique_classes:
            indices = class_indices[c]
            fold_size = len(indices) // self.k
            
            for fold_id in range(self.k):
                start = fold_id * fold_size
                end = start + fold_size if fold_id < self.k - 1 else len(indices)
                fold_indices[fold_id].extend(indices[start:end])
        
        # Generate train/test splits
        splits = []
        for test_fold in range(self.k):
            test_indices = fold_indices[test_fold]
            train_indices = []
            for fold_id in range(self.k):
                if fold_id != test_fold:
                    train_indices.extend(fold_indices[fold_id])
            
            splits.append((sorted(train_indices), sorted(test_indices)))
        
        return splits

class CrossValidator:
    """Performs k-fold cross-validation evaluation."""
    
    def __init__(self, k: int = 5, seed: int = 42):
        """Initialize cross-validator.
        
        Args:
            k: Number of folds.
            seed: Random seed.
        """
        self.k = k
        self.seed = seed
        self.splitter = StratifiedKFoldSplitter(k, seed)
    
    def evaluate(
        self,
        scores: List[float],
        labels: List[int],
        threshold: float = 0.5,
        compute_auc: bool = True,
    ) -> CrossValidationResult:
        """Perform k-fold cross-validation.
        
        Args:
            scores: Similarity scores for pairs.
            labels: Ground truth labels (0 or 1).
            threshold: Decision threshold.
            compute_auc: Whether to compute ROC and PR AUC.
            
        Returns:
            CrossValidationResult with metrics for each fold.
        """
        scores_arr = np.array(scores)
        labels_arr = np.array(labels)
        
        # Generate stratified splits
        splits = self.splitter.split(len(scores), labels)
        
        fold_results: List[FoldMetrics] = []
        all_f1 = []
        all_precision = []
        all_recall = []
        
        for fold_id, (train_idx, test_idx) in enumerate(splits):
            train_idx = np.array(train_idx)
            test_idx = np.array(test_idx)
            
            # Get test fold data
            test_scores = scores_arr[test_idx]
            test_labels = labels_arr[test_idx]
            
            # Compute decisions
            decisions = (test_scores >= threshold).astype(int)
            
            # Compute confusion matrix
            tp = np.sum((decisions == 1) & (test_labels == 1))
            fp = np.sum((decisions == 1) & (test_labels == 0))
            tn = np.sum((decisions == 0) & (test_labels == 0))
            fn = np.sum((decisions == 0) & (test_labels == 1))
            
            # Compute metrics
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            # Compute AUC if requested
            roc_auc = 0.0
            pr_auc = 0.0
            if compute_auc and len(np.unique(test_labels)) > 1:
                from sklearn.metrics import roc_auc_score, average_precision_score
                try:
                    roc_auc = float(roc_auc_score(test_labels, test_scores))
                except Exception:
                    roc_auc = 0.0
                
                try:
                    pr_auc = float(average_precision_score(test_labels, test_scores))
                except Exception:
                    pr_auc = 0.0
            
            all_f1.append(f1)
            all_precision.append(precision)
            all_recall.append(recall)
            
            fold_results.append(FoldMetrics(
                fold_id=fold_id,
                precision=precision,
                recall=recall,
                f1=f1,
                roc_auc=roc_auc,
                pr_auc=pr_auc,
                tp=int(tp),
                fp=int(fp),
                tn=int(tn),
                fn=int(fn),
                n_samples=len(test_idx),
            ))
        
        # Compute aggregate statistics
        f1_arr = np.array(all_f1)
        precision_arr = np.array(all_precision)
        recall_arr = np.array(all_recall)
        
        mean_f1 = float(np.mean(f1_arr))
        std_f1 = float(np.std(f1_arr))
        mean_precision = float(np.mean(precision_arr))
        std_precision = float(np.std(precision_arr))
        mean_recall = float(np.mean(recall_arr))
        std_recall = float(np.std(recall_arr))
        
        # Compute 95% confidence intervals
        ci_f1 = self._compute_ci(f1_arr)
        ci_precision = self._compute_ci(precision_arr)
        ci_recall = self._compute_ci(recall_arr)
        
        # Compute fold stability (CV = std / mean)
        fold_stability = std_f1 / (mean_f1 + 1e-6) if mean_f1 > 0 else 0.0
        
        return CrossValidationResult(
            k=self.k,
            fold_results=fold_results,
            mean_f1=mean_f1,
            std_f1=std_f1,
            mean_precision=mean_precision,
            std_precision=std_precision,
            mean_recall=mean_recall,
            std_recall=std_recall,
            ci_f1=ci_f1,
            ci_precision=ci_precision,
            ci_recall=ci_recall,
            fold_stability=fold_stability,
        )
    
    def _compute_ci(
        self, 
        values: np.ndarray, 
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Compute confidence interval using t-distribution.
        
        Args:
            values: Array of values.
            confidence: Confidence level (e.g., 0.95 for 95%).
            
        Returns:
            Tuple of (ci_lower, ci_upper).
        """
        from scipy import stats
        
        mean = np.mean(values)
        std_err = np.std(values) / np.sqrt(len(values))
        
        # t-critical value for (k-1) degrees of freedom
        df = len(values) - 1
        t_crit = stats.t.ppf((1 + confidence) / 2, df)
        
        ci_lower = mean - t_crit * std_err
        ci_upper = mean + t_crit * std_err
        
        return (float(ci_lower), float(ci_upper))

def cross_validate_benchmark(
    scores_dict: Dict[str, List[float]],
    labels: List[int],
    k: int = 5,
    threshold: float = 0.5,
) -> Dict[str, CrossValidationResult]:
    """Cross-validate multiple tools/engines.
    
    Args:
        scores_dict: Dictionary mapping tool names to score lists.
        labels: Ground truth labels.
        k: Number of folds.
        threshold: Decision threshold.
        
    Returns:
        Dictionary mapping tool names to cross-validation results.
    """
    validator = CrossValidator(k=k, seed=42)
    results = {}
    
    for tool_name, scores in scores_dict.items():
        results[tool_name] = validator.evaluate(scores, labels, threshold)
    
    return results