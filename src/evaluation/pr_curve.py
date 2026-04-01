"""PR Curve - threshold sweep and optimal threshold selection."""
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class PRPoint:
    threshold: float; precision: float; recall: float; f1: float; f2: float

def compute_pr_curve(predictions: List[Dict], truth_pairs: List[Dict],
                     num_points: int = 1000, beta: float = 2.0) -> List[PRPoint]:
    from evaluation.metrics import compute_metrics
    label_map = {}
    for gt in truth_pairs:
        k = tuple(sorted([gt.get("file1",""), gt.get("file2","")]))
        label_map[k] = gt.get("label", 0)
    beta2 = beta ** 2
    points = []
    for i in range(num_points + 1):
        th = i / num_points
        m = compute_metrics(predictions, label_map, th)
        f2 = ((1+beta2)*m.precision*m.recall/(beta2*m.precision+m.recall)) if (beta2*m.precision+m.recall) else 0
        points.append(PRPoint(threshold=th, precision=m.precision, recall=m.recall, f1=m.f1, f2=f2))
    return points

def optimal_threshold(points: List[PRPoint], method: str = "f2") -> PRPoint:
    return max(points, key=lambda p: p.f2 if method == "f2" else p.f1)
