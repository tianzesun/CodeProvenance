"""Similarity scoring algorithms for code comparison.

Core similarity detection algorithms:
- Token-based (winnowing)
- AST-based (structural analysis)
- Hybrid (weighted combination)
- BaseSimilarityEngine: Strict interface that all engines MUST implement
"""

# Raw algorithms
from .token_winnowing import token_similarity
from .ast_subtree import compare_ast, ast_similarity, compare_ast_safe
from .hybrid import HybridSimilarity, HybridSimilarityConfig

# Strict engine interface (THE contract - no engine allowed outside this)
from .base_engine import BaseSimilarityEngine, SimilarityScore

# Concrete engine implementations
from .engines import (
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