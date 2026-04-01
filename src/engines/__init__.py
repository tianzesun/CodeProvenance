"""Engines - unified computation layer."""
from src.engines.base_engine import BaseEngine, EngineResult
__all__ = ['BaseEngine', 'EngineResult', 'BaseSimilarityAlgorithm', 'SimilarityEngine', 'FusionEngine', 'FeatureExtractor']

def __getattr__(name):
    if name == 'FusionEngine':
        from src.engines.scoring import FusionEngine
        return FusionEngine
    if name == 'FeatureExtractor':
        from src.engines.features import FeatureExtractor
        return FeatureExtractor
    if name in ('BaseSimilarityAlgorithm', 'SimilarityEngine'):
        from src.engines.similarity import BaseSimilarityAlgorithm
        return BaseSimilarityAlgorithm
    raise AttributeError(name)
