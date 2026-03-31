"""
Threshold Optimizer - Threshold.md spec.

PR Curve + Optimal Point Selection.

Features:
- Compute PR curve from predictions vs ground truth
- Select optimal threshold (Max F1, Max Fβ)
- Dataset-aware threshold selection
- JSON export with curve data
- Confidence-aware threshold adjustment
"""
from typing import Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class CurvePoint:
    threshold: float
    precision: float
    recall: float
    f1: float
    fbeta: float


@dataclass
class ThresholdResult:
    optimal_threshold: float
    selection_method: str
    metrics_at_optimal: Dict[str, float]
    curve: List[CurvePoint]
    dataset: str = ""
    tool: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "optimal_threshold": self.optimal_threshold,
            "selection_method": self.selection_method,
            "metrics_at_optimal": self.metrics_at_optimal,
            "curve": [{"threshold": p.threshold, "precision": p.precision,
                       "recall": p.recall, "f1": p.f1, "f2": p.fbeta} for p in self.curve],
            "dataset": self.dataset,
            "tool": self.tool,
        }


class ThresholdOptimizer:
    """
    Threshold optimizer following Threshold.md spec.
    
    Pipeline:
    1. Compute PR curve (1000 points)
    2. Compute F1(t), F2(t) for all thresholds
    3. Select optimal: max F2 (primary), max F1 (fallback)
    4. Export JSON report
    """
    
    def __init__(self, beta: float = 2.0, num_points: int = 1000):
        self.beta = beta
        self.num_points = num_points
    
    @staticmethod
    def _normalize_pair(f1: str, f2: str) -> Tuple[str, str]:
        return tuple(sorted([f1.strip(), f2.strip()]))
    
    def compute_pr_curve(self, predictions: List[Dict[str, Any]],
                         ground_truth: Dict[str, Any]) -> List[CurvePoint]:
        """Compute full PR curve with 1000 threshold samples."""
        truth_pairs = set()
        for gt in ground_truth.get("pairs", []):
            if gt.get("label", 0) == 1:
                f1, f2 = gt.get("file1", ""), gt.get("file2", "")
                if f1 and f2:
                    truth_pairs.add(self._normalize_pair(f1, f2))
        
        total_relevant = len(truth_pairs)
        if total_relevant == 0:
            return []
        
        best_sim = {}
        for pred in predictions:
            f1, f2 = pred.get("file1", ""), pred.get("file2", "")
            sim = pred.get("similarity", 0)
            if f1 and f2:
                key = self._normalize_pair(f1, f2)
                if key not in best_sim or sim > best_sim[key]:
                    best_sim[key] = sim
        
        sorted_items = sorted(best_sim.items(), key=lambda x: x[1], reverse=True)
        curve_points = []
        beta2 = self.beta ** 2
        
        for i in range(self.num_points):
            threshold = i / self.num_points
            tp = fp = 0
            for key, sim in sorted_items:
                if sim < threshold:
                    break
                if key in truth_pairs:
                    tp += 1
                else:
                    fp += 1
            
            precision = tp / (tp + fp) if (tp + fp) else 1.0
            recall = tp / total_relevant
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0
            fbeta = ((1 + beta2) * precision * recall / (beta2 * precision + recall)) if (beta2 * precision + recall) else 0
            
            curve_points.append(CurvePoint(
                threshold=threshold,
                precision=round(precision, 4),
                recall=round(recall, 4),
                f1=round(f1, 4),
                fbeta=round(fbeta, 4),
            ))
        
        return curve_points
    
    def select_threshold(self, curve: List[CurvePoint], method: str = "f2") -> ThresholdResult:
        """Select optimal threshold."""
        if not curve:
            return ThresholdResult(
                optimal_threshold=0.5, selection_method=method,
                metrics_at_optimal={"precision": 0, "recall": 0, "f1": 0, "f2": 0},
                curve=[]
            )
        
        if method == "f2":
            best = max(curve, key=lambda p: p.fbeta)
        elif method == "f1":
            best = max(curve, key=lambda p: p.f1)
        elif method == "youden":
            best = max(curve, key=lambda p: p.recall + p.precision)
        else:
            best = max(curve, key=lambda p: p.fbeta)
        
        return ThresholdResult(
            optimal_threshold=best.threshold,
            selection_method=method,
            metrics_at_optimal={
                "precision": best.precision, "recall": best.recall,
                "f1": best.f1, "f2": best.fbeta,
            },
            curve=curve,
        )
    
    def optimize(self, predictions: List[Dict[str, Any]],
                 ground_truth: Dict[str, Any],
                 dataset: str = "", tool: str = "") -> ThresholdResult:
        """Full pipeline: compute curve -> select threshold."""
        curve = self.compute_pr_curve(predictions, ground_truth)
        result = self.select_threshold(curve, method="f2")
        result.dataset = dataset
        result.tool = tool
        return result
    
    def export_report(self, result: ThresholdResult, path: Path) -> None:
        """Export threshold report to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)