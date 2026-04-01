"""Engines Layer - algorithm plugins with formal registry."""
from src.engines.base import BaseSimilarityEngine, BaseFeatureExtractor
from src.engines.registry import EngineRegistry
__all__ = ['BaseSimilarityEngine', 'BaseFeatureExtractor', 'EngineRegistry']
