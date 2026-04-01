"""Evaluator - PURE ONLINE metrics computation only. NO decision influence."""
from typing import Dict, List, Any, Tuple
from src.evaluation.metrics import Metrics, compute_metrics

class Evaluator:
    """Offline evaluation only. NEVER affects runtime decisions."""
    def evaluate(self, predictions: List[Dict], label_map: Dict[str, int], threshold: float = 0.5) -> Metrics:
        """Compute metrics only."""
        return compute_metrics(predictions, label_map, threshold)
    def analyze(self, predictions: List[Dict], truth: List[Dict]) -> Tuple[Metrics, Dict]:
        """Offline analysis."""
        label_map = {tuple(sorted([gt.get("file1",""), gt.get("file2","")])): gt.get("label",0) for gt in truth}
        m = compute_metrics(predictions, label_map, 0.5)
        fp, fn = [], []
        pred_set = {}
        for p in predictions:
            k = tuple(sorted([p.get("file1",""), p.get("file2","")]))
            sim = p.get("similarity", 0)
            if k not in pred_set or sim > pred_set[k]:
                pred_set[k] = sim
        for k, v in label_map.items():
            score = pred_set.get(k, 0)
            if score >= 0.5 and not v:
                fp.append(list(k))
            elif score < 0.5 and v:
                fn.append(list(k))
        return m, {"fp": fp, "fn": fn}
