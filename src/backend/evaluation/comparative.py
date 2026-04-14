"""Comparative evaluation for multi-engine comparison.

Allows comparing multiple detection engines against each other and ground truth.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class EngineResult:
    """Result from a single engine evaluation."""
    engine_name: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    map_score: float = 0.0
    mrr_score: float = 0.0
    total_comparisons: int = 0


@dataclass
class ComparativeReport:
    """Comparative evaluation report."""
    engine_results: List[EngineResult] = field(default_factory=list)
    best_engine: str = ""
    best_metric: str = "f1"

    def rank_by(self, metric: str = "f1") -> List[EngineResult]:
        """Rank engines by a specific metric.
        
        Args:
            metric: Metric to rank by (f1, precision, recall, etc.)
            
        Returns:
            Sorted list of EngineResult objects.
        """
        return sorted(
            self.engine_results,
            key=lambda x: getattr(x, metric, 0),
            reverse=True
        )

    @property
    def best_engine(self) -> str:
        """Get the best performing engine."""
        if not self.engine_results:
            return ""
        ranked = self.rank_by(self.best_metric)
        return ranked[0].engine_name if ranked else ""


def evaluate_comparative(
    engine_results: Dict[str, Dict[str, float]]
) -> ComparativeReport:
    """Evaluate and compare multiple engines.
    
    Args:
        engine_results: Dict mapping engine name to metrics dict.
        
    Returns:
        ComparativeReport with ranked results.
    """
    report = ComparativeReport()
    
    for name, metrics in engine_results.items():
        report.engine_results.append(EngineResult(
            engine_name=name,
            precision=metrics.get('precision', 0.0),
            recall=metrics.get('recall', 0.0),
            f1=metrics.get('f1', 0.0),
            accuracy=metrics.get('accuracy', 0.0),
            map_score=metrics.get('map', 0.0),
            mrr_score=metrics.get('mrr', 0.0),
            total_comparisons=metrics.get('total_comparisons', 0)
        ))
    
    return report


def find_best_threshold(
    scores_and_labels: List[tuple],
    metric: str = "f1"
) -> tuple:
    """Find optimal threshold for a given metric.
    
    Args:
        scores_and_labels: List of (score, label) tuples.
        metric: Metric to optimize (f1, precision, recall).
        
    Returns:
        Tuple of (best_threshold, best_score).
    """
    best_threshold = 0.5
    best_score = 0.0
    
    for t in [i / 100 for i in range(0, 101)]:
        tp = fp = fn = tn = 0
        for score, label in scores_and_labels:
            predicted = 1 if score >= t else 0
            if predicted == 1 and label == 1:
                tp += 1
            elif predicted == 1 and label == 0:
                fp += 1
            elif predicted == 0 and label == 1:
                fn += 1
            else:
                tn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        current_score = {'precision': precision, 'recall': recall, 'f1': f1}.get(metric, f1)
        
        if current_score > best_score:
            best_score = current_score
            best_threshold = t
    
    return best_threshold, best_score