"""Clone type breakdown analysis for benchmark results.

Analyzes performance by clone type (Type-1/2/3/4/Non-Clone) to identify
strengths and weaknesses of each detection engine.

Clone Type Metrics:
- Type-1: Exact clones (identical code)
- Type-2: Renamed identifiers
- Type-3: Restructured code
- Type-4: Semantic clones (same meaning, different syntax)
- Non-clone: Negative samples

For each clone type (1-4):
- TP: actual is this clone type AND predicted as clone
- FP: predicted as clone BUT actual is NOT this clone type
- FN: actual is this clone type BUT predicted as non-clone

This gives per-type precision = TP / (TP + FP)
and per-type recall = TP / (TP + FN)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from benchmark.metrics import precision as calc_precision, recall as calc_recall, f1_score


@dataclass
class CloneTypeMetrics:
    """Metrics for a specific clone type.
    
    For clone types 1-4:
    - precision: proportion of predictions for this type that are correct
    - recall: proportion of actual pairs of this type that were detected
    
    For non_clone (0):
    - precision: 1.0 if no false positives, else 1 - fp_rate
    - recall: proportion of non-clones correctly classified
    """
    clone_type: int  # 1-4 for clones, 0 for non-clone
    tp: int = 0
    fp: int = 0
    fn: int = 0
    total_predicted_clone: int = 0  # Total predicted as clone (for FP tracking)
    total_actual_this_type: int = 0  # Total actually this type
    scores: List[float] = field(default_factory=list)
    labels: List[int] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        return self.tp + self.fn
    
    @property
    def precision(self) -> float:
        return calc_precision(self.tp, self.fp)
    
    @property
    def recall(self) -> float:
        return calc_recall(self.tp, self.fn)
    
    @property
    def f1(self) -> float:
        return f1_score(self.precision, self.recall)
    
    @property
    def accuracy(self) -> float:
        total = self.tp + self.fp + self.fn
        return self.tp / total if total > 0 else 1.0


@dataclass
class CloneTypeBreakdown:
    """Complete breakdown by clone type."""
    engine_name: str
    types: Dict[int, CloneTypeMetrics] = field(default_factory=dict)
    top_false_positives: List[Dict] = field(default_factory=list)
    
    def get_type(self, clone_type: int) -> CloneTypeMetrics:
        if clone_type not in self.types:
            self.types[clone_type] = CloneTypeMetrics(clone_type=clone_type)
        return self.types[clone_type]
    
    def summary_dict(self) -> Dict[str, Dict[str, float]]:
        """Return summary as nested dict for JSON."""
        result = {}
        type_names = {0: "non_clone", 1: "type1", 2: "type2", 3: "type3", 4: "type4"}
        for ct in sorted(self.types.keys()):
            metrics = self.types[ct]
            name = type_names.get(ct, f"type_{ct}")
            result[name] = {
                "actual_count": metrics.total_actual_this_type,
                "count": metrics.count,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
                "accuracy": metrics.accuracy,
                "tp": metrics.tp,
                "fp": metrics.fp,
                "fn": metrics.fn,
            }
        return result


def analyze_clone_type_breakdown(
    results: List,  # List of SimilarityResult
    ground_truth: Dict,
    pair_clone_types: Dict[Tuple[str, str], int],
    threshold: float = 0.5
) -> CloneTypeBreakdown:
    """Analyze performance breakdown by clone type.
    
    For each clone type (1-4):
    - TP: correctly detected clone AND actual is that clone type
    - FP: predicted as clone but NOT that type (includes non-clones and other types)
    - FN: actual is that clone type but NOT detected
    
    For non_clone (0):
    - TP: correctly classified as non-clone (predicted non-clone AND actual non-clone)
    - FP: actual non-clone but predicted clone (false alarm)
    - FN: N/A
    
    Args:
        results: List of similarity results.
        ground_truth: Ground truth mapping (id_a, id_b) -> label.
        pair_clone_types: Mapping of (id_a, id_b) -> clone_type.
        threshold: Decision threshold.
        
    Returns:
        CloneTypeBreakdown with per-type metrics.
    """
    breakdown = CloneTypeBreakdown(engine_name="unknown")
    
    # Initialize all types
    for ct in range(5):
        breakdown.get_type(ct)
    
    # Temporary storage for FP tracking
    fps_for_types: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    top_fps: List[Dict] = []
    
    for r in results:
        key = (r.id_a, r.id_b)
        label = ground_truth.get(key, ground_truth.get((r.id_b, r.id_a), 0))
        clone_type = pair_clone_types.get(key, pair_clone_types.get((r.id_b, r.id_a), 0))
        predicted = 1 if r.score >= threshold else 0
        
        metrics = breakdown.get_type(clone_type)
        metrics.scores.append(r.score)
        metrics.labels.append(label)
        metrics.total_actual_this_type += 1
        
        if label == 1:  # Actual clone
            if predicted == 1:
                # Correctly detected as clone
                metrics.tp += 1
            else:
                # Clone not detected (FN for this type)
                metrics.fn += 1
        else:  # Actual non-clone
            if predicted == 1:
                # FALSE POSITIVE: non-clone predicted as clone
                # This counts as FP for ALL clone types (1-4)
                for ct in range(1, 5):
                    breakdown.types[ct].fp += 1
                # Track as top FP
                top_fps.append({
                    "file_a": r.id_a,
                    "file_b": r.id_b,
                    "similarity_score": r.score,
                    "threshold": threshold,
                })
    
    # Sort by score descending (most confident false alarms first)
    top_fps.sort(key=lambda x: x["similarity_score"], reverse=True)
    breakdown.top_false_positives = top_fps[:10]  # Top 10 FPs
    
    return breakdown