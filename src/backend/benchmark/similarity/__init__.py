"""Similarity scoring algorithms for code comparison.

Core similarity detection algorithms:
- Token-based (winnowing)
- AST-based (structural analysis)
- Hybrid (weighted combination)
- BaseSimilarityEngine: Strict interface that all engines MUST implement
"""

# Raw algorithms
from .ast_subtree import ast_similarity, compare_ast, compare_ast_safe

# Strict engine interface (THE contract - no engine allowed outside this)
from .base_engine import BaseSimilarityEngine, SimilarityScore

# Concrete engine implementations
from .engines import (
    ASTEngine,
    HybridEngine,
    TokenWinnowingEngine,
)
from .hybrid import HybridSimilarity, HybridSimilarityConfig
from .token_winnowing import token_similarity

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