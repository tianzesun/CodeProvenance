"""Legacy re-export for AST similarity."""

from src.backend.engines.similarity.ast_similarity import (
    ASTNode,
    ASTSimilarity,
    ControlFlowGraph,
    DataFlowGraph,
    TreeEditDistance,
)

__all__ = [
    "ASTNode",
    "ASTSimilarity",
    "ControlFlowGraph",
    "DataFlowGraph",
    "TreeEditDistance",
]
