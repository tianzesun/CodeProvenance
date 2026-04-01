"""Engines - pure computation, stateless only."""
from src.engines.base_engine import BaseEngine, EngineResult

__all__ = ['BaseEngine', 'EngineResult', 'BaseSimilarityAlgorithm', 'SimilarityEngine', 'FusionEngine']

def __getattr__(name):
    if name == 'FusionEngine':
        from src.engines.fusion import FusionEngine
        return FusionEngine
    if name in ('BaseSimilarityAlgorithm', 'SimilarityEngine'):
        from src.engines.similarity import BaseSimilarityAlgorithm, SimilarityEngine
        if name == 'BaseSimilarityAlgorithm':
            return BaseSimilarityAlgorithm
        return SimilarityEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")