"""Similarity scoring algorithms for code comparison.

Core similarity detection algorithms:
- Token-based (winnowing)
- AST-based (structural analysis)
- Hybrid (weighted combination)
- BaseSimilarityEngine: Strict interface that all engines MUST implement
"""

# Raw algorithms
from benchmark.similarity.token_winnowing import token_similarity
from benchmark.similarity.ast_subtree import compare_ast, ast_similarity, compare_ast_safe
from benchmark.similarity.hybrid import HybridSimilarity, HybridSimilarityConfig

# Strict engine interface (THE contract - no engine allowed outside this)
from benchmark.similarity.base_engine import BaseSimilarityEngine, SimilarityScore

# Concrete engine implementations
from benchmark.similarity.engines import (
    TokenWinnowingEngine,
    ASTEngine,
    HybridEngine,
)

__all__ = [
    # Raw algorithms
    'token_similarity',
    'compare_ast',
    'compare_ast_safe',
    'ast_similarity',
    'HybridSimilarity',
    'HybridSimilarityConfig',
    # Engine interface
    'BaseSimilarityEngine',
    'SimilarityScore',
    # Concrete engines
    'TokenWinnowingEngine',
    'ASTEngine',
    'HybridEngine',
]