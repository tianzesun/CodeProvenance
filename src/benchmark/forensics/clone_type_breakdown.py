"""Clone Type Breakdown Analysis for code similarity detection.

Provides detailed analysis of performance broken down by clone type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Define SimilarityResult locally to avoid circular import with pipeline.stages
@dataclass
class SimilarityResult:
    """Result of a similarity comparison."""
    id_a: str
    id_b: str
    score: float  # [0, 1]
    label: Optional[int] = None
    engine_name: str = ""
    clone_type: int = 0  # 1-4 for clones, 0 for non-clone


@dataclass
class CloneTypeBreakdown:
    """Breakdown of performance metrics by clone type.
    
    Attributes:
        engine_name: Name of the engine.
        type1: Metrics for Type-1 clones (identical).
        type2: Metrics for Type-2 clones (renamed).
        type3: Metrics for Type-3 clones (restructured).
        type4: Metrics for Type-4 clones (semantic).
        non_clone: Metrics for non-clone pairs.
    """
    engine_name: str = ""
    type1: Dict[str, float] = field(default_factory=dict)
    type2: Dict[str, float] = field(default_factory=dict)
    type3: Dict[str, float] = field(default_factory=dict)
    type4: Dict[str, float] = field(default_factory=dict)
    non_clone: Dict[str, float] = field(default_factory=dict)
    
    def summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "engine_name": self.engine_name,
            "type1": self.type1,
            "type2": self.type2,
            "type3": self.type3,
            "type4": self.type4,
            "non_clone": self.non_clone,
        }
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            f"CLONE TYPE BREAKDOWN - {self.engine_name}",
            "=" * 70,
            "",
            "TYPE-1 (IDENTICAL):",
            f"  Precision: {self.type1.get('precision', 0.0):.4f}",
            f"  Recall:    {self.type1.get('recall', 0.0):.4f}",
            f"  F1:        {self.type1.get('f1', 0.0):.4f}",
            "",
            "TYPE-2 (RENAMED):",
            f"  Precision: {self.type2.get('precision', 0.0):.4f}",
            f"  Recall:    {self.type2.get('recall', 0.0):.4f}",
            f"  F1:        {self.type2.get('f1', 0.0):.4f}",
            "",
            "TYPE-3 (RESTRUCTURED):",
            f"  Precision: {self.type3.get('precision', 0.0):.4f}",
            f"  Recall:    {self.type3.get('recall', 0.0):.4f}",
            f"  F1:        {self.type3.get('f1', 0.0):.4f}",
            "",
            "TYPE-4 (SEMANTIC):",
            f"  Precision: {self.type4.get('precision', 0.0):.4f}",
            f"  Recall:    {self.type4.get('recall', 0.0):.4f}",
            f"  F1:        {self.type4.get('f1', 0.0):.4f}",
            "",
            "NON-CLONE:",
            f"  Precision: {self.non_clone.get('precision', 0.0):.4f}",
            f"  Recall:    {self.non_clone.get('recall', 0.0):.4f}",
            f"  F1:        {self.non_clone.get('f1', 0.0):.4f}",
            "",
            "=" * 70,
        ]
        return "\n".join(lines)


def analyze_clone_type_breakdown(
    results: List[SimilarityResult],
    ground_truth: Dict[Tuple[str, str], int],
    pair_clone_types: Dict[Tuple[str, str], int],
    threshold: float = 0.5,
) -> CloneTypeBreakdown:
    """Analyze performance broken down by clone type.
    
    Args:
        results: List of similarity results.
        ground_truth: Ground truth mapping (pair -> label).
        pair_clone_types: Mapping of pair to clone type.
        threshold: Decision threshold.
        
    Returns:
        CloneTypeBreakdown with per-type metrics.
    """
    breakdown = CloneTypeBreakdown()
    
    # Initialize counters for each clone type
    type_counters = {
        1: {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        2: {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        3: {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        4: {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        0: {"tp": 0, "fp": 0, "fn": 0, "tn": 0},  # non-clone
    }
    
    for result in results:
        pair_key = (result.id_a, result.id_b)
        reverse_key = (result.id_b, result.id_a)
        
        # Get ground truth label
        label = ground_truth.get(pair_key, ground_truth.get(reverse_key, 0))
        
        # Get clone type
        clone_type = pair_clone_types.get(pair_key, pair_clone_types.get(reverse_key, 0))
        
        # Ensure clone_type is in valid range
        if clone_type not in type_counters:
            clone_type = 0
        
        # Make prediction
        predicted = 1 if result.score >= threshold else 0
        
        # Update counters
        if predicted == 1 and label == 1:
            type_counters[clone_type]["tp"] += 1
        elif predicted == 1 and label == 0:
            type_counters[clone_type]["fp"] += 1
        elif predicted == 0 and label == 1:
            type_counters[clone_type]["fn"] += 1
        else:  # predicted == 0 and label == 0
            type_counters[clone_type]["tn"] += 1
    
    # Calculate metrics for each clone type
    for clone_type, counters in type_counters.items():
        tp = counters["tp"]
        fp = counters["fp"]
        fn = counters["fn"]
        tn = counters["tn"]
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
        
        metrics = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "accuracy": accuracy,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "total": tp + fp + fn + tn,
        }
        
        if clone_type == 1:
            breakdown.type1 = metrics
        elif clone_type == 2:
            breakdown.type2 = metrics
        elif clone_type == 3:
            breakdown.type3 = metrics
        elif clone_type == 4:
            breakdown.type4 = metrics
        else:  # clone_type == 0 (non-clone)
            breakdown.non_clone = metrics
    
    return breakdown