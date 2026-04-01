"""Benchmark metrics module.

Provides all evaluation metrics required for scientific benchmark:
- Classification: Precision, Recall, F1, Accuracy
- Ranking: MAP, MRR, NDCG, Top-K Precision
"""
from typing import Dict, List, Tuple, Optional
import math


# =============================================================================
# Classification Metrics
# =============================================================================

def precision(tp: int, fp: int) -> float:
    """Calculate precision.
    
    Args:
        tp: True positives count.
        fp: False positives count.
        
    Returns:
        Precision score between 0.0 and 1.0.
    """
    return tp / (tp + fp) if (tp + fp) > 0 else 0.0


def recall(tp: int, fn: int) -> float:
    """Calculate recall.
    
    Args:
        tp: True positives count.
        fn: False negatives count.
        
    Returns:
        Recall score between 0.0 and 1.0.
    """
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def f1_score(prec: float, rec: float) -> float:
    """Calculate F1 score.
    
    Args:
        prec: Precision score.
        rec: Recall score.
        
    Returns:
        F1 score between 0.0 and 1.0.
    """
    return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0


def accuracy(tp: int, tn: int, fp: int, fn: int) -> float:
    """Calculate accuracy.
    
    Args:
        tp: True positives count.
        tn: True negatives count.
        fp: False positives count.
        fn: False negatives count.
        
    Returns:
        Accuracy score between 0.0 and 1.0.
    """
    total = tp + tn + fp + fn
    return (tp + tn) / total if total > 0 else 0.0


def confusion_matrix(
    predictions: List[Tuple[str, str, int]],
    ground_truth: Dict[Tuple[str, str], int]
) -> Dict[str, int]:
    """Calculate confusion matrix values.
    
    Args:
        predictions: List of (file1, file2, predicted_label).
        ground_truth: Dict of (file1, file2) -> label.
        
    Returns:
        Dict with tp, tn, fp, fn counts.
    """
    result = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    
    for f1, f2, pred in predictions:
        actual = ground_truth.get((f1, f2), ground_truth.get((f2, f1), 0))
        if pred == 1 and actual == 1:
            result["tp"] += 1
        elif pred == 0 and actual == 0:
            result["tn"] += 1
        elif pred == 1 and actual == 0:
            result["fp"] += 1
        elif pred == 0 and actual == 1:
            result["fn"] += 1
            
    return result


def compute_classification_metrics(
    tp: int, fp: int, tn: int, fn: int
) -> Dict[str, float]:
    """Compute all classification metrics at once.
    
    Args:
        tp: True positives count.
        fp: False positives count.
        tn: True negatives count.
        fn: False negatives count.
        
    Returns:
        Dict with precision, recall, f1, accuracy.
    """
    prec = precision(tp, fp)
    rec = recall(tp, fn)
    f1 = f1_score(prec, rec)
    acc = accuracy(tp, tn, fp, fn)
    
    return {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "accuracy": acc
    }


# =============================================================================
# Ranking Metrics
# =============================================================================

def mean_average_precision(
    query_results: Dict[str, List[Tuple[str, float, int]]]
) -> float:
    """Calculate Mean Average Precision (MAP).
    
    Args:
        query_results: Dict mapping query_id to list of (doc_id, score, relevance).
        
    Returns:
        MAP score between 0.0 and 1.0.
    """
    if not query_results:
        return 0.0
    
    aps = []
    for query_id, results in query_results.items():
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
        relevant_count = 0
        precision_sum = 0.0
        
        for i, (_, _, relevance) in enumerate(sorted_results):
            if relevance == 1:
                relevant_count += 1
                precision_sum += relevant_count / (i + 1)
        
        total_relevant = sum(1 for _, _, r in sorted_results if r == 1)
        ap = precision_sum / total_relevant if total_relevant > 0 else 0.0
        aps.append(ap)
    
    return sum(aps) / len(aps) if aps else 0.0


def mean_reciprocal_rank(
    query_results: Dict[str, List[Tuple[str, float, int]]]
) -> float:
    """Calculate Mean Reciprocal Rank (MRR).
    
    Args:
        query_results: Dict mapping query_id to list of (doc_id, score, relevance).
        
    Returns:
        MRR score between 0.0 and 1.0.
    """
    if not query_results:
        return 0.0
    
    rrs = []
    for query_id, results in query_results.items():
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
        
        for i, (_, _, relevance) in enumerate(sorted_results):
            if relevance == 1:
                rrs.append(1.0 / (i + 1))
                break
        else:
            rrs.append(0.0)
    
    return sum(rrs) / len(rrs) if rrs else 0.0


def top_k_precision(
    query_results: Dict[str, List[Tuple[str, float, int]]],
    k: int = 10
) -> float:
    """Calculate Top-K Precision.
    
    Args:
        query_results: Dict mapping query_id to list of (doc_id, score, relevance).
        k: Number of top results to consider.
        
    Returns:
        Top-K precision score between 0.0 and 1.0.
    """
    if not query_results:
        return 0.0
    
    precisions = []
    for query_id, results in query_results.items():
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)[:k]
        relevant = sum(1 for _, _, r in sorted_results if r == 1)
        precisions.append(relevant / min(k, len(results)))
    
    return sum(precisions) / len(precisions) if precisions else 0.0


def ndcg_at_k(
    query_results: Dict[str, List[Tuple[str, float, int]]],
    k: int = 10
) -> float:
    """Calculate Normalized Discounted Cumulative Gain at K.
    
    Args:
        query_results: Dict mapping query_id to list of (doc_id, score, relevance).
        k: Number of top results to consider.
        
    Returns:
        NDCG score between 0.0 and 1.0.
    """
    if not query_results:
        return 0.0
    
    ndcgs = []
    for query_id, results in query_results.items():
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)[:k]
        
        dcg = 0.0
        for i, (_, _, relevance) in enumerate(sorted_results):
            dcg += (2 ** relevance - 1) / math.log2(i + 2)
        
        ideal_sorted = sorted(results, key=lambda x: x[2], reverse=True)[:k]
        idcg = 0.0
        for i, (_, _, relevance) in enumerate(ideal_sorted):
            idcg += (2 ** relevance - 1) / math.log2(i + 2)
        
        ndcg = dcg / idcg if idcg > 0 else 0.0
        ndcgs.append(ndcg)
    
    return sum(ndcgs) / len(ndcgs) if ndcgs else 0.0


def compute_ranking_metrics(
    query_results: Dict[str, List[Tuple[str, float, int]]],
    k: int = 10
) -> Dict[str, float]:
    """Compute all ranking metrics at once.
    
    Args:
        query_results: Dict mapping query_id to list of (doc_id, score, relevance).
        k: Top-K value for precision and NDCG.
        
    Returns:
        Dict with map, mrr, top_k_precision, ndcg.
    """
    return {
        "map": mean_average_precision(query_results),
        "mrr": mean_reciprocal_rank(query_results),
        f"top_{k}_precision": top_k_precision(query_results, k),
        f"ndcg@{k}": ndcg_at_k(query_results, k)
    }


__all__ = [
    # Classification
    'precision',
    'recall',
    'f1_score',
    'accuracy',
    'confusion_matrix',
    'compute_classification_metrics',
    # Ranking
    'mean_average_precision',
    'mean_reciprocal_rank',
    'top_k_precision',
    'ndcg_at_k',
    'compute_ranking_metrics',
]