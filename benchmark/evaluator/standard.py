"""
Standardized Benchmark Evaluator.

PRO5.md strict semantics:
- Pair = (file1, file2), canonicalized as sorted tuple (A,B) == (B,A)
- similarity >= threshold -> Positive (use >=, not >)
- Deduplicate: keep max similarity per pair
- File-level evaluation (not submission-level)
- MOSS asymmetry: use min(A->B, B->A)
- Fixed threshold evaluation with PR curve support
- Output FP/FN lists for training
"""
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import csv
import json
from datetime import datetime


@dataclass
class EvaluationResult:
    """Evaluation result with detailed analysis."""
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int
    tn: int
    total_pairs: int
    false_positives: List[Tuple[str, str]] = field(default_factory=list)
    false_negatives: List[Tuple[str, str]] = field(default_factory=list)
    true_positives: List[Tuple[str, str]] = field(default_factory=list)
    threshold: float = 0.5


@dataclass
class PRPoint:
    """A point on the Precision-Recall curve."""
    threshold: float
    precision: float
    recall: float
    f1: float


class BenchmarkEvaluator:
    """
    Strict PRO5.md evaluator for comparing tool outputs against ground truth.
    
    Evaluation rules:
    1. Canonicalize pairs: (A,B) == (B,A) -> sorted tuple
    2. similarity >= threshold -> Positive
    3. Deduplicate: keep max similarity per pair
    4. File-level evaluation
    5. Fixed threshold (default 0.5)
    """
    
    @staticmethod
    def _normalize_pair(f1: str, f2: str) -> Tuple[str, str]:
        """Canonicalize pair to sorted tuple (A,B) where A <= B."""
        return tuple(sorted([f1.strip(), f2.strip()]))
    
    @staticmethod
    def evaluate(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        threshold: float = 0.5,
        include_details: bool = True
    ) -> EvaluationResult:
        """
        Evaluate predictions against ground truth.
        
        Args:
            predictions: List of {"file1": ..., "file2": ..., "similarity": ...}
            ground_truth: {"pairs": [{"file1": ..., "file2": ..., "label": 0|1}]}
            threshold: similarity >= threshold -> Positive (use >=)
            include_details: Whether to compute FP/FN lists
            
        Returns:
            EvaluationResult with precision, recall, f1, and detailed lists
        """
        # Step 1: Build ground truth sets
        truth_pairs: Set[Tuple[str, str]] = set()  # All pairs with label=1
        non_truth_pairs: Set[Tuple[str, str]] = set()  # All pairs with label=0
        
        for gt_pair in ground_truth.get("pairs", []):
            label = gt_pair.get("label", 0)
            f1 = gt_pair.get("file1", "").strip()
            f2 = gt_pair.get("file2", "").strip()
            if f1 and f2:
                key = BenchmarkEvaluator._normalize_pair(f1, f2)
                if label == 1:
                    truth_pairs.add(key)
                else:
                    non_truth_pairs.add(key)
        
        # Step 2: Build predicted set with thresholding
        # Deduplicate: keep max similarity per pair
        best_sim: Dict[Tuple[str, str], float] = {}
        for pred in predictions:
            f1 = pred.get("file1", "").strip()
            f2 = pred.get("file2", "").strip()
            sim = pred.get("similarity", 0)
            if f1 and f2:
                key = BenchmarkEvaluator._normalize_pair(f1, f2)
                if key not in best_sim or sim > best_sim[key]:
                    best_sim[key] = sim
        
        # Apply threshold: >= threshold -> Positive
        predicted_pairs: Set[Tuple[str, str]] = set()
        for key, sim in best_sim.items():
            if sim >= threshold:  # Use >= (not >)
                predicted_pairs.add(key)
        
        # Step 3: Compute TP, FP, FN
        tp_set = predicted_pairs & truth_pairs
        fp_set = predicted_pairs - truth_pairs
        fn_set = truth_pairs - predicted_pairs
        
        # TN: pairs that are NOT in truth and NOT predicted
        # This includes all (non_truth_pairs) plus any unobserved pairs
        # For benchmark purposes, TN = non_truth_pairs that were predicted as negative
        tn_set = (non_truth_pairs - predicted_pairs)
        
        tp = len(tp_set)
        fp = len(fp_set)
        fn = len(fn_set)
        tn = len(tn_set)
        
        # Step 4: Compute metrics
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        
        result = EvaluationResult(
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            tp=tp, fp=fp, fn=fn, tn=tn,
            total_pairs=len(truth_pairs) + len(non_truth_pairs),
            threshold=threshold,
        )
        
        if include_details:
            result.true_positives = list(tp_set)
            result.false_positives = list(fp_set)
            result.false_negatives = list(fn_set)
        
        return result
    
    @staticmethod
    def pr_curve(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        num_points: int = 50
    ) -> List[PRPoint]:
        """
        Generate Precision-Recall curve points.
        
        Sweeps threshold from 0.0 to 1.0.
        
        Args:
            predictions: List of prediction dicts
            ground_truth: Ground truth dict
            num_points: Number of threshold points
            
        Returns:
            List of PRPoint
        """
        points = []
        
        for i in range(num_points + 1):
            threshold = i / num_points
            result = BenchmarkEvaluator.evaluate(
                predictions, ground_truth, threshold, include_details=False
            )
            points.append(PRPoint(
                threshold=threshold,
                precision=result.precision,
                recall=result.recall,
                f1=result.f1,
            ))
        
        return points
    
    @staticmethod
    def optimal_threshold(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        metric: str = "f1"
    ) -> Tuple[float, float]:
        """
        Find optimal threshold for a given metric.
        
        Args:
            predictions: List of prediction dicts
            ground_truth: Ground truth dict
            metric: "f1", "precision", or "recall"
            
        Returns:
            (optimal_threshold, best_metric_value)
        """
        curve = BenchmarkEvaluator.pr_curve(predictions, ground_truth)
        best_point = max(curve, key=lambda p: getattr(p, metric, 0))
        return best_point.threshold, getattr(best_point, metric, 0)


class ReportWriter:
    """Writes benchmark reports in CSV and JSON formats."""
    
    def __init__(self, report_dir: Path = Path("benchmark/reports")):
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def save_csv(
        self, results: Dict[str, EvaluationResult],
        filename: str = "results"
    ) -> Path:
        """Save CSV comparison report with strict table format."""
        path = self.report_dir / f"{filename}.csv"
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["tool", "precision", "recall", "f1", "tp", "fp", "fn", "tn"])
            for tool, r in results.items():
                writer.writerow([tool, r.precision, r.recall, r.f1, r.tp, r.fp, r.fn, r.tn])
        return path
    
    def save_json(
        self, experiment: str, dataset: str,
        results: Dict[str, EvaluationResult],
        include_fp_fn: bool = True
    ) -> Path:
        """Save detailed JSON report with FP/FN lists."""
        path = self.report_dir / f"{experiment}_{dataset}_report.json"
        data = {
            "experiment": experiment,
            "dataset": dataset,
            "timestamp": datetime.now().isoformat(),
            "results": {},
        }
        
        for tool, r in results.items():
            entry = {
                "precision": r.precision, "recall": r.recall, "f1": r.f1,
                "tp": r.tp, "fp": r.fp, "fn": r.fn, "tn": r.tn,
                "threshold": r.threshold,
            }
            if include_fp_fn:
                entry["false_positives"] = [list(p) for p in r.false_positives]
                entry["false_negatives"] = [list(p) for p in r.false_negatives]
            data["results"][tool] = entry
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return path
    
    def save_pr_curve(
        self, experiment: str, dataset: str,
        tool_name: str, points: List[PRPoint]
    ) -> Path:
        """Save PR curve as JSON."""
        path = self.report_dir / f"{experiment}_{dataset}_{tool_name}_pr.json"
        data = {
            "tool": tool_name, "experiment": experiment, "dataset": dataset,
            "pr_curve": [{"threshold": p.threshold, "precision": p.precision,
                          "recall": p.recall, "f1": p.f1} for p in points],
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return path