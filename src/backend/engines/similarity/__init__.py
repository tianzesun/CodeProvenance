"""Similarity Engines - pure computation via registry."""
from src.backend.engines.similarity.registry import SimilarityRegistry
__all__ = ['SimilarityRegistry', 'BaseSimilarityAlgorithm', 'SimilarityEngine']

def __getattr__(name):
    if name in ('BaseSimilarityAlgorithm', 'SimilarityEngine', 'register_builtin_algorithms'):
        from src.backend.engines.similarity.base_similarity import BaseSimilarityAlgorithm
        return BaseSimilarityAlgorithm
    raise AttributeError(name)
