"""Benchmark evaluation module.

Provides evaluation logic for pairwise, ranking, comparative, and threshold optimization.
"""
from benchmark.evaluation.pairwise import (
    evaluate_pairwise,
    aggregate_pairwise_results,
    PairwiseResult
)
from benchmark.evaluation.ranking import (
    mean_average_precision,
    mean_reciprocal_rank,
    top_k_precision,
    ndcg_at_k
)
from benchmark.evaluation.comparative import (
    evaluate_comparative,
    find_best_threshold,
    ComparativeReport,
    EngineResult
)

__all__ = [
    'evaluate_pairwise',
    'aggregate_pairwise_results',
    'PairwiseResult',
    'mean_average_precision',
    'mean_reciprocal_rank',
    'top_k_precision',
    'ndcg_at_k',
    'evaluate_comparative',
    'find_best_threshold',
    'ComparativeReport',
    'EngineResult'
]