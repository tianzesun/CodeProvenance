"""Evaluator - Full evaluation with metrics + FP/FN lists."""
from typing import Dict, List, Any, Tuple
from src.evaluation.metrics import Metrics, compute_metrics

class Evaluator:
    """Centralized evaluation engine."""
    def evaluate(self, predictions: List[Dict[str, Any]], truth_pairs: List[Dict],
                 threshold: float = 0.5) -> Tuple[Metrics, Dict]:
        label_map = {}
        for gt in truth_pairs:
            k = tuple(sorted([gt.get("file1",""), gt.get("file2","")]))
            label_map[k] = gt.get("label", 0)
        metrics = compute_metrics(predictions, label_map, threshold)
        fp_pairs, fn_pairs = [], []
        pred_set = {}
        for p in predictions:
            k = tuple(sorted([p.get("file1",""), p.get("file2","")]))
            sim = p.get("similarity", 0)
            if k not in pred_set or sim > pred_set[k]:
                pred_set[k] = sim
        for k, v in label_map.items():
            score = pred_set.get(k, 0)
            pred = 1 if score >= threshold else 0
            if pred and not v:
                fp_pairs.append(list(k))
            elif not pred and v:
                fn_pairs.append(list(k))
        return metrics, {"fp": fp_pairs, "fn": fn_pairs}
