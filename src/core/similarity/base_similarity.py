"""Legacy re-export for the similarity engine base module."""

from src.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms

__all__ = ["SimilarityEngine", "register_builtin_algorithms"]
