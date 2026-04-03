"""Ranking evaluation metrics.

Provides MAP, MRR, and Top-K precision for similarity ranking evaluation.
"""
from typing import List, Dict, Tuple, Set
import math


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


def reciprocal_rank_fusion(
    engine_results: List[Dict[str, float]],
    k: int = 60
) -> Dict[str, float]:
    """
    Combines rankings from multiple engines using Reciprocal Rank Fusion (RRF).
    
    RRF score for a document d is:
    RRFscore(d) = sum_{r in rankings} 1 / (k + rank(d, r))
    
    Args:
        engine_results: List of dictionaries mapping doc_id to similarity score.
        k: Smoothing constant (default 60 as per literature).
        
    Returns:
        Dictionary mapping doc_id to fused RRF score.
    """
    rrf_scores: Dict[str, float] = {}
    
    for engine_scores in engine_results:
        # Sort documents by score to get rankings
        sorted_docs = sorted(engine_scores.items(), key=lambda x: x[1], reverse=True)
        
        for rank, (doc_id, _) in enumerate(sorted_docs):
            # Rank is 1-based
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
            
    return rrf_scores
