"""Pairwise comparison evaluation.

Handles pairwise code similarity evaluation with ground truth comparison.
"""
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass


@dataclass
class PairwiseResult:
    """Result of a pairwise comparison."""
    file1: str
    file2: str
    similarity_score: float
    predicted_label: int
    actual_label: int
    engine: str

    @property
    def is_correct(self) -> bool:
        return self.predicted_label == self.actual_label

    @property
    def is_tp(self) -> bool:
        return self.predicted_label == 1 and self.actual_label == 1

    @property
    def is_fp(self) -> bool:
        return self.predicted_label == 1 and self.actual_label == 0

    @property
    def is_tn(self) -> bool:
        return self.predicted_label == 0 and self.actual_label == 0

    @property
    def is_fn(self) -> bool:
        return self.predicted_label == 0 and self.actual_label == 1


def evaluate_pairwise(
    predictions: List[Dict[str, Any]],
    ground_truth: Dict[Tuple[str, str], int],
    threshold: float = 0.5
) -> List[PairwiseResult]:
    """Evaluate pairwise predictions against ground truth.
    
    Args:
        predictions: List of prediction dicts with file1, file2, score.
        ground_truth: Dict mapping (file1, file2) tuples to labels.
        threshold: Similarity threshold for classification.
        
    Returns:
        List of PairwiseResult objects.
    """
    results = []
    for pred in predictions:
        f1, f2 = pred['file1'], pred['file2']
        score = pred['score']
        predicted = 1 if score >= threshold else 0
        
        actual = ground_truth.get((f1, f2), ground_truth.get((f2, f1), 0))
        
        results.append(PairwiseResult(
            file1=f1,
            file2=f2,
            similarity_score=score,
            predicted_label=predicted,
            actual_label=actual,
            engine=pred.get('engine', 'unknown')
        ))
    return results


def aggregate_pairwise_results(results: List[PairwiseResult]) -> Dict[str, Any]:
    """Aggregate pairwise results into summary statistics.
    
    Args:
        results: List of PairwiseResult objects.
        
    Returns:
        Dictionary with aggregated statistics.
    """
    tp = sum(1 for r in results if r.is_tp)
    fp = sum(1 for r in results if r.is_fp)
    tn = sum(1 for r in results if r.is_tn)
    fn = sum(1 for r in results if r.is_fn)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(results) if results else 0.0
    
    return {
        'tp': tp,
        'fp': fp,
        'tn': tn,
        'fn': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'accuracy': accuracy,
        'total_comparisons': len(results)
    }