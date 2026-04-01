"""Similarity implementations - lazy load to avoid numpy import at startup."""
__all__ = ['BaseSimilarityAlgorithm', 'SimilarityEngine', 'register_builtin_algorithms']

def _sim():
    from src.engines.similarity.base_similarity import BaseSimilarityAlgorithm, SimilarityEngine, register_builtin_algorithms
    return BaseSimilarityAlgorithm, SimilarityEngine, register_builtin_algorithms

def __getattr__(name):
    if name in __all__:
        return _sim()[__all__.index(name)]
    raise AttributeError(name)
