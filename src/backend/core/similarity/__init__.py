"""Compatibility exports for legacy similarity imports."""

from src.backend.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
from src.backend.engines.similarity.token_similarity import TokenSimilarity
from src.backend.engines.similarity.ast_similarity import (
    ASTNode,
    ASTSimilarity,
    ControlFlowGraph,
    DataFlowGraph,
    TreeEditDistance,
)
from src.backend.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity

__all__ = [
    "ASTNode",
    "ASTSimilarity",
    "ControlFlowGraph",
    "DataFlowGraph",
    "EnhancedWinnowingSimilarity",
    "SimilarityEngine",
    "TokenSimilarity",
    "TreeEditDistance",
    "register_builtin_algorithms",
]
