"""Compatibility exports for legacy similarity imports."""

from src.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
from src.engines.similarity.token_similarity import TokenSimilarity
from src.engines.similarity.ast_similarity import (
    ASTNode,
    ASTSimilarity,
    ControlFlowGraph,
    DataFlowGraph,
    TreeEditDistance,
)
from src.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity

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
