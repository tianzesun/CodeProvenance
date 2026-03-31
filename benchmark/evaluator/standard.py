"""Standardized benchmark evaluator."""
from typing import Dict, List, Any, Set, Tuple
from pathlib import Path
import csv
import json
from datetime import datetime


class BenchmarkEvaluator:
    """
    Standardized evaluator for comparing tool outputs against ground truth.
    
    Core logic:
    1. Binarize: similarity >= threshold -> 1, else -> 0
    2. Build sets: Predicted = {(f1, f2)}, Truth = {(f1, f2)}
    3. TP, FP, FN calculation
    4. Precision, Recall, F1
    """
    
    @staticmethod
    def _normalize_pair(f1: str, f2: str) -> Tuple[str, str]:
        return tuple(sorted([f1, f2]))
    
    @staticmethod
    def evaluate(
        predictions: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Evaluate predictions against ground truth.
        
        Args:
            predictions: List of {"file1": ..., "file2": ..., "similarity": ...}
            ground_truth: Dict with "clones" and "non_clones" sets or pairs with labels
            threshold: Similarity threshold for binarization
            
        Returns:
            {"precision": ..., "recall": ..., "f1": ...}
        """
        # Step 1: Binarize and build predicted set
        predicted: Set[Tuple[str, str]] = set()
        for p in predictions:
            sim = p.get("similarity", 0)
            if sim >= threshold:
                f1, f2 = p.get("file1", ""), p.get("file2", "")
                if f1 and f2:
                    predicted.add(BenchmarkEvaluator._normalize_pair(f1, f2))
        
        # Step 2: Build truth set (file1, file2 pairs where label=1)
        truth: Set[Tuple[str, str]] = set()
        for gt_pair in ground_truth.get("pairs", []):
            if gt_pair.get("label", 0) == 1:
                f1, f2 = gt_pair.get("file1", ""), gt_pair.get("file2", "")
                truth.add(BenchmarkEvaluator._normalize_pair(f1, f2))
        
        # Step 3: Calculate TP, FP, FN
        tp_set = predicted & truth
        fp_set = predicted - truth
        fn_set = truth - predicted
        
        tp = len(tp_set)
        fp = len(fp_set)
        fn = len(fn_set)
        
        # Step 4: Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "total_predicted": len(predicted),
            "total_truth": len(truth),
        }


class ReportWriter:
    """Writes benchmark reports in CSV and JSON formats."""
    
    def __init__(self, report_dir: Path = Path("benchmark/reports")):
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def save_csv(self, results: Dict[str, Dict[str, Any]], filename: str = "results") -> Path:
        """Save CSV comparison report."""
        path = self.report_dir / f"{filename}.csv"
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["tool", "precision", "recall", "f1"])
            for tool, metrics in results.items():
                writer.writerow([tool, metrics.get("precision",0), metrics.get("recall",0), metrics.get("f1",0)])
        return path
    
    def save_json(self, experiment: str, dataset: str, results: Dict[str, Dict[str, Any]]) -> Path:
        """Save detailed JSON report."""
        path = self.report_dir / f"{experiment}_{dataset}_report.json"
        data = {
            "experiment": experiment,
            "dataset": dataset,
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return path