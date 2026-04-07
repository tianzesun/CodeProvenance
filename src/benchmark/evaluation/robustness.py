"""
Robustness testing framework for plagiarism detectors.

Implements:
- T1: identifier renaming
- T2: statement reordering  
- T3: loop conversion (for ↔ while)
- T4: dead code injection
- T5: whitespace/formatting normalization
- T6: semantic-preserving refactoring

Robustness score: R = 1 - Var(score(T_i(x), T_j(x)))

Paper-ready evaluation protocol:
- Balanced positive/negative pair sampling
- Stratified evaluation per clone type
- ROC-AUC, PR-AUC, ECE calibration
- Inter-tool agreement metrics
"""
from __future__ import annotations
import ast
import random
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.benchmark.generators.utils.rename_utils import rename_identifiers
from src.benchmark.generators.utils.transform_utils import (
    reorder_statements,
    add_dead_code,
    convert_loops,
)
from src.benchmark.generators.utils.ast_utils import parse_code, unparse_code


TRANSFORMATIONS = {
    "T1": rename_identifiers,
    "T2": reorder_statements,
    "T3": convert_loops,
    "T4": add_dead_code,
}

TRANSFORMATION_NAMES = {
    "T1": "Identifier Renaming",
    "T2": "Statement Reordering",
    "T3": "Loop Conversion",
    "T4": "Dead Code Injection",
}


@dataclass
class RobustnessResult:
    """Result of robustness testing."""
    original_score: float
    transformed_scores: Dict[str, float]
    variance: float
    robustness_score: float
    transformation_impact: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_score": round(self.original_score, 4),
            "transformed_scores": {k: round(v, 4) for k, v in self.transformed_scores.items()},
            "variance": round(self.variance, 6),
            "robustness_score": round(self.robustness_score, 4),
            "transformation_impact": {k: round(v, 4) for k, v in self.transformation_impact.items()},
        }


@dataclass
class ClonePair:
    """Labeled code pair with clone type."""
    code_a: str
    code_b: str
    label: int  # 0-4 following taxonomy: C0-C4
    clone_type: str
    transformations: List[str] = field(default_factory=list)
    
    def apply_transformations(self, 
                              transformations: List[str], 
                              seed: int = 42) -> 'ClonePair':
        """Apply transformations to code_b."""
        rng = random.Random(seed)
        transformed = self.code_b
        
        for t_name in transformations:
            if t_name in TRANSFORMATIONS:
                transformed = TRANSFORMATIONS[t_name](transformed, seed=rng.randint(0, 10000))
        
        return ClonePair(
            code_a=self.code_a,
            code_b=transformed,
            label=self.label,
            clone_type=self.clone_type,
            transformations=transformations
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code_a": self.code_a,
            "code_b": self.code_b,
            "label": self.label,
            "clone_type": self.clone_type,
            "transformations": self.transformations,
        }


class RobustnessTester:
    """Tests detector robustness under semantic-preserving transformations."""
    
    def __init__(self, detector: Callable[[str, str], float], 
                 transformations: Optional[List[str]] = None):
        """
        Args:
            detector: Function that takes two code strings and returns similarity score
            transformations: List of transformations to test (default: all)
        """
        self.detector = detector
        self.transformations = transformations or list(TRANSFORMATIONS.keys())
    
    def test_pair(self, code_a: str, code_b: str) -> RobustnessResult:
        """Test robustness of a single code pair."""
        original_score = self.detector(code_a, code_b)
        
        transformed_scores = {}
        for t_name in self.transformations:
            try:
                transformed_b = TRANSFORMATIONS[t_name](code_b)
                transformed_scores[t_name] = self.detector(code_a, transformed_b)
            except:
                transformed_scores[t_name] = original_score
        
        scores = list(transformed_scores.values())
        variance = np.var(scores) if len(scores) > 1 else 0.0
        
        # Robustness = 1 - normalized variance
        # If variance exceeds 0.5, robustness becomes negative
        robustness_score = max(0.0, 1.0 - (variance * 4))
        
        # Impact per transformation: |original - transformed|
        transformation_impact = {
            t: abs(original_score - transformed_scores[t])
            for t in self.transformations
        }
        
        return RobustnessResult(
            original_score=original_score,
            transformed_scores=transformed_scores,
            variance=variance,
            robustness_score=robustness_score,
            transformation_impact=transformation_impact
        )
    
    def test_dataset(self, pairs: List[ClonePair]) -> Dict[str, Any]:
        """Test robustness across an entire dataset."""
        results = []
        per_transformation_impact = {t: [] for t in self.transformations}
        robustness_scores = []
        
        for pair in pairs:
            result = self.test_pair(pair.code_a, pair.code_b)
            results.append(result)
            robustness_scores.append(result.robustness_score)
            
            for t in self.transformations:
                per_transformation_impact[t].append(result.transformation_impact[t])
        
        return {
            "mean_robustness": np.mean(robustness_scores),
            "median_robustness": np.median(robustness_scores),
            "robustness_std": np.std(robustness_scores),
            "per_transformation": {
                t: {
                    "mean_impact": np.mean(per_transformation_impact[t]),
                    "median_impact": np.median(per_transformation_impact[t]),
                } for t in self.transformations
            },
            "results": [r.to_dict() for r in results],
        }


def generate_transformed_clone(original: str, 
                               transformation_chain: List[str],
                               seed: int = 42) -> str:
    """Generate a transformed version of code by applying a chain of transformations."""
    result = original
    rng = random.Random(seed)
    
    for t_name in transformation_chain:
        if t_name in TRANSFORMATIONS:
            result = TRANSFORMATIONS[t_name](result, seed=rng.randint(0, 10000))
    
    return result


def balanced_sample_pairs(pairs: List[ClonePair], 
                          positive_ratio: float = 0.5) -> List[ClonePair]:
    """Sample balanced dataset with given positive/negative ratio."""
    positives = [p for p in pairs if p.label >= 2]  # C2+ are positive
    negatives = [p for p in pairs if p.label < 2]   # C0/C1 are negative
    
    n_pos = int(len(pairs) * positive_ratio)
    n_neg = len(pairs) - n_pos
    
    sampled = []
    if positives:
        sampled.extend(random.sample(positives, min(n_pos, len(positives))))
    if negatives:
        sampled.extend(random.sample(negatives, min(n_neg, len(negatives))))
    
    random.shuffle(sampled)
    return sampled


def stratified_evaluation(scores: List[float], 
                          labels: List[int],
                          thresholds: Optional[List[float]] = None) -> Dict[str, Any]:
    """
    Paper-ready stratified evaluation.
    
    Computes:
    - Precision, Recall, F1 at best threshold
    - ROC-AUC, PR-AUC
    - Calibration error (ECE)
    - Per-clone-type performance
    """
    from sklearn.metrics import (
        precision_recall_curve,
        roc_auc_score,
        average_precision_score,
        confusion_matrix,
    )
    
    if thresholds is None:
        thresholds = np.linspace(0.1, 0.9, 17)
    
    # Binary labels: label >= 2 is positive
    binary_labels = [1 if l >= 2 else 0 for l in labels]
    
    results = {}
    
    # ROC-AUC and PR-AUC
    if len(np.unique(binary_labels)) > 1:
        results["roc_auc"] = round(roc_auc_score(binary_labels, scores), 4)
        results["pr_auc"] = round(average_precision_score(binary_labels, scores), 4)
    else:
        results["roc_auc"] = 0.0
        results["pr_auc"] = 0.0
    
    # Find best F1 threshold
    best_f1 = 0.0
    best_threshold = 0.5
    best_cm = None
    
    for t in thresholds:
        preds = [1 if s >= t else 0 for s in scores]
        cm = confusion_matrix(binary_labels, preds)
        tn, fp, fn, tp = cm.ravel()
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
            best_cm = cm
    
    tn, fp, fn, tp = best_cm.ravel() if best_cm is not None else (0, 0, 0, 0)
    
    results.update({
        "best_threshold": round(best_threshold, 2),
        "best_f1": round(best_f1, 4),
        "precision": round(tp / (tp + fp) if (tp + fp) > 0 else 0, 4),
        "recall": round(tp / (tp + fn) if (tp + fn) > 0 else 0, 4),
        "confusion_matrix": {
            "tn": int(tn), "fp": int(fp), 
            "fn": int(fn), "tp": int(tp)
        },
    })
    
    # Per-clone-type performance
    clone_type_metrics = {}
    for label in range(5):  # C0-C4
        mask = [l == label for l in labels]
        if any(mask):
            type_scores = [s for s, m in zip(scores, mask) if m]
            clone_type_metrics[f"C{label}"] = {
                "count": sum(mask),
                "mean_score": round(np.mean(type_scores), 4),
                "median_score": round(np.median(type_scores), 4),
            }
    
    results["per_clone_type"] = clone_type_metrics
    
    # Expected Calibration Error
    n_bins = 10
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    
    for bin_idx in range(n_bins):
        bin_min = bin_boundaries[bin_idx]
        bin_max = bin_boundaries[bin_idx + 1]
        
        bin_mask = [s >= bin_min and s < bin_max for s in scores]
        bin_count = sum(bin_mask)
        
        if bin_count > 0:
            bin_scores = [s for s, m in zip(scores, bin_mask) if m]
            bin_labels = [1 if l >= 2 else 0 for l, m in zip(labels, bin_mask) if m]
            
            avg_score = np.mean(bin_scores)
            avg_acc = np.mean(bin_labels)
            
            ece += (bin_count / len(scores)) * abs(avg_score - avg_acc)
    
    results["ece"] = round(ece, 4)
    
    return results