"""Concrete engine implementations that implement BaseSimilarityEngine.

These are the canonical engines for the benchmark system.
Each engine wraps the raw similarity functions behind the strict interface.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base_engine import BaseSimilarityEngine
from .token_winnowing import token_similarity


class TokenWinnowingEngine(BaseSimilarityEngine):
    """Token-based similarity engine using winnowing algorithm.
    
    Detects Type-1 (exact) and Type-2 (renamed) clones.
    """
    
    def __init__(
        self,
        k: int = 6,
        window_size: int = 4
    ):
        self._k = k
        self._window_size = window_size
    
    @property
    def name(self) -> str:
        return "token_winnowing_v1"
    
    def compare(self, code_a: str, code_b: str) -> float:
        if not code_a or not code_b:
            return 0.0
        return token_similarity(code_a, code_b, k=self._k, window_size=self._window_size)
    
    def configure(self, **kwargs: Any) -> None:
        self._k = kwargs.get("k", self._k)
        self._window_size = kwargs.get("window_size", self._window_size)


class ASTEngine(BaseSimilarityEngine):
    """AST-based structural similarity engine.
    
    Detects structural similarities in code.
    """
    
    def __init__(self, max_depth: int = 3):
        self._max_depth = max_depth
    
    @property
    def name(self) -> str:
        return "ast_structural_v1"
    
    def compare(self, code_a: str, code_b: str) -> float:
        if not code_a or not code_b:
            return 0.0
        try:
            from src.backend.benchmark.similarity.ast_subtree import compare_ast_safe
            return compare_ast_safe(code_a, code_b, max_depth=self._max_depth)
        except ImportError:
            return 0.0
    
    def configure(self, **kwargs: Any) -> None:
        self._max_depth = kwargs.get("max_depth", self._max_depth)


class HybridEngine(BaseSimilarityEngine):
    """Hybrid similarity engine combining token and AST similarity.
    
    Provides weighted combination of multiple similarity measures.
    """
    
    def __init__(
        self,
        token_weight: float = 0.6,
        ast_weight: float = 0.4,
        token_k: int = 6,
        token_window: int = 4,
        ast_max_depth: int = 3,
    ):
        self._token_weight = token_weight
        self._ast_weight = ast_weight
        self._token_k = token_k
        self._token_window = token_window
        self._ast_max_depth = ast_max_depth
    
    @property
    def name(self) -> str:
        return "hybrid_v1"
    
    def compare(self, code_a: str, code_b: str) -> float:
        if not code_a or not code_b:
            return 0.0
        
        # Token-based similarity
        token_sim = token_similarity(
            code_a, code_b,
            k=self._token_k,
            window_size=self._token_window
        )
        
        # AST-based similarity (best-effort without parser)
        try:
            from src.backend.benchmark.similarity.ast_subtree import compare_ast_safe
            ast_sim = compare_ast_safe(
                code_a, code_b,
                max_depth=self._ast_max_depth
            )
        except ImportError:
            ast_sim = 0.0
        
        total_weight = self._token_weight + self._ast_weight
        if total_weight == 0:
            return 0.0
        
        return (
            token_sim * self._token_weight +
            ast_sim * self._ast_weight
        ) / total_weight
    
    def configure(self, **kwargs: Any) -> None:
        self._token_weight = kwargs.get("token_weight", self._token_weight)
        self._ast_weight = kwargs.get("ast_weight", self._ast_weight)
        self._token_k = kwargs.get("token_k", self._token_k)
        self._token_window = kwargs.get("token_window", self._token_window)
        self._ast_max_depth = kwargs.get("ast_max_depth", self._ast_max_depth)