"""Core Metrics - Production safe computation."""
from typing import Dict, List

def compute_metrics(predictions: List[Dict], label_map: Dict[str, int], threshold: float = 0.5) -> Dict[str, float]:
    """Compute P/R/F1."""
    tp = fp = fn = tn = 0
    for p in predictions:
        score = p.get("similarity", 0)
        pair_key = tuple(sorted([p.get("file1",""), p.get("file2","")]))
        pred = 1 if score >= threshold else 0
        truth = label_map.get(pair_key, -1)
        if truth < 0: continue
        if pred and truth: tp += 1
        elif pred and not truth: fp += 1
        elif not pred and truth: fn += 1
        else: tn += 1
    prec = tp/(tp+fp) if (tp+fp) else 0
    rec = tp/(tp+fn) if (tp+fn) else 0
    f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}
