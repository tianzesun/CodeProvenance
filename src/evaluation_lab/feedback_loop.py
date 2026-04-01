"""Feedback Loop Pipeline - FN/FP → threshold optimization → deploy.

Pure Python implementation - no numpy dependency.
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json

@dataclass
class ThresholdConfig:
    T_high: float
    T_low: float
    weights: Dict[str, float]
    version: str
    created_at: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self): return self.__dict__
    @staticmethod
    def from_dict(d): return ThresholdConfig(**d)

class PRPoint:
    def __init__(self, t, p, r, f): self.threshold, self.precision, self.recall, self.f1 = t, p, r, f
    def to_dict(self): return {"threshold": self.threshold, "precision": self.precision, "recall": self.recall, "f1": self.f1}

def _linspace(a, b, n): return [a + i*(b-a)/(n-1) for i in range(n)]

class ThresholdOptimizer:
    def __init__(self, n_points: int = 50): self.n_points = n_points
    def compute_pr_curve(self, scores: List[float], labels: List[int]) -> List[PRPoint]:
        curve = []
        for t in _linspace(0.5, 0.95, self.n_points):
            tp = fp = fn = tn = 0
            for s, l in zip(scores, labels):
                pr = 1 if s >= t else 0
                if l and pr: tp += 1
                elif l and not pr: fn += 1
                elif not l and pr: fp += 1
                else: tn += 1
            prec = tp/(tp+fp) if (tp+fp) else 0
            rec = tp/(tp+fn) if (tp+fn) else 0
            f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0
            curve.append(PRPoint(t, prec, rec, f1))
        return curve
    def find_best_f1(self, curve): return max(curve, key=lambda p: p.f1)
    def find_precision_first(self, curve, min_prec=0.9):
        valid = [p for p in curve if p.precision >= min_prec]
        return max(valid, key=lambda p: p.recall) if valid else None
    def optimize_dual_threshold(self, scores, labels, high_r=(0.7,0.95), low_r=(0.5,0.8)):
        best, best_p = 0, (0.8, 0.6)
        for th in _linspace(*high_r, 20):
            for tl in _linspace(*low_r, 20):
                if tl >= th: continue
                tp_h=tp_s=fp_h=fp_s=fn=0
                for s, l in zip(scores, labels):
                    pr = 2 if s >= th else (1 if s >= tl else 0)
                    if l: fn += (pr==0); tp_h += (pr==2); tp_s += (pr==1)
                    else: fp_h += (pr==2); fp_s += (pr==1)
                tp, fp = tp_h+tp_s, fp_h+fp_s
                f1 = 2*tp/(2*tp+fp+fn) if (2*tp+fp+fn) else 0
                if f1 > best: best, best_p = f1, (th, tl)
        return best_p

class FeedbackLoopPipeline:
    def __init__(self, output_dir="config/thresholds"):
        self.optimizer = ThresholdOptimizer()
        self.output_dir = output_dir
        import os; os.makedirs(output_dir, exist_ok=True)
    def run(self, scores, labels, weights, strategy="max_f1"):
        curve = self.optimizer.compute_pr_curve(scores, labels)
        if strategy == "precision_first":
            best = self.optimizer.find_precision_first(curve)
            th = tl = best.threshold if best else 0.7
        elif strategy == "dual":
            th, tl = self.optimizer.optimize_dual_threshold(scores, labels)
        else:
            best = self.optimizer.find_best_f1(curve)
            th = tl = best.threshold
        tp=fp=fn=tn=0
        for s, l in zip(scores, labels):
            pr = 1 if s >= (tl if strategy!="dual" else th) else 0
            if l and pr: tp += 1
            elif l and not pr: fn += 1
            elif not l and pr: fp += 1
            else: tn += 1
        prec = tp/(tp+fp) if (tp+fp) else 0
        rec = tp/(tp+fn) if (tp+fn) else 0
        f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0
        version = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-v1"
        config = ThresholdConfig(T_high=th, T_low=tl, weights=weights, version=version,
            created_at=datetime.now(timezone.utc).isoformat(),
            metrics={"precision":prec, "recall":rec, "f1":f1, "tp":tp, "fp":fp, "fn":fn, "tn":tn,
                     "pr_curve": [p.to_dict() for p in curve]})
        with open(f"{self.output_dir}/{version}.json", 'w') as f: json.dump(config.__dict__, f, indent=2)
        return config
