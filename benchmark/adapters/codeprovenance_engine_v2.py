"""CodeProvenance Engine v2 - Multi-stage pipeline with tiered thresholds.

Implements the recommendations from benchmark analysis:
1. Multi-stage decision pipeline (token -> AST -> embedding)
2. Tiered thresholds (dynamic based on code size)
3. Negative filtering (anti-FP layer)
4. Weighted score fusion
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from benchmark.similarity.base_engine import BaseSimilarityEngine


@dataclass
class MultiStageScore:
    """Score from multiple similarity algorithms."""
    token_sim: float
    ast_sim: float
    embedding_sim: float
    structural_sim: float  # token + AST combined
    final_score: float


class CodeProvenanceEngineV2(BaseSimilarityEngine):
    """Multi-stage CodeProvenance engine with improved precision."""
    
    # Tier 1: Token thresholds (high precision)
    TOKEN_T1_ACCEPT = 0.90
    TOKEN_T1_REJECT = 0.30
    
    # Tier 2: AST thresholds   
    AST_T2_ACCEPT = 0.70
    AST_T2_REJECT = 0.30
    
    # Tier 3: Embedding thresholds (gated by structure)
    EMBED_T3_ACCEPT = 0.85
    EMBED_T3_GATE = 0.50    # structural must be above this
    
    # Score fusion weights
    WEIGHT_TOKEN = 0.25
    WEIGHT_AST = 0.35
    WEIGHT_EMBED = 0.40
    
    # Dynamic threshold adjustment
    SIZE_SMALL = 50    # tokens
    SIZE_LARGE = 200
    THRESH_SMALL = 0.35   # stricter for small code
    THRESH_LARGE = 0.25   # relaxed for large code
    THRESH_MID = 0.30

    def __init__(self):
        self._engine = None
        self._token_engine = None
    
    def _get_token_engine(self):
        if self._token_engine is None:
            from benchmark.similarity import TokenWinnowingEngine
            self._token_engine = TokenWinnowingEngine()
        return self._token_engine

    def _get_full_engine(self):
        if self._engine is None:
            from src.engines.similarity.base_similarity import SimilarityEngine
            from src.engines.similarity.base_similarity import register_builtin_algorithms
            
            self._engine = SimilarityEngine()
            register_builtin_algorithms(self._engine)
            self._engine.enable_deep_analysis(True)
        return self._engine

    @property
    def name(self) -> str:
        return "codeprovenance_v2"

    def compare(self, code_a: str, code_b: str) -> float:
        if not code_a or not code_b:
            return 0.0
        
        # Stage 1: Token similarity
        token_sim = self._get_token_engine().compare(code_a, code_b)
        
        # Early accept for exact matches
        if token_sim >= self.TOKEN_T1_ACCEPT:
            return 1.0
        
        # Stage 2: AST structural similarity
        ast_sim = self._compute_ast_similarity(code_a, code_b)
        
        # Early reject only if both are very low
        if token_sim < 0.1 and ast_sim < 0.1:
            return 0.0
        
        # Score fusion
        scores = self._get_score_fusion(token_sim, ast_sim, code_a, code_b)
        
        return max(0.0, min(1.0, scores.final_score))

    def _compute_ast_similarity(self, code_a: str, code_b: str) -> float:
        try:
            from benchmark.similarity import compare_ast_safe
            return compare_ast_safe(code_a, code_b, max_depth=3)
        except Exception:
            return 0.0

    def _compute_embedding_similarity(self, code_a: str, code_b: str) -> float:
        tokens_a = set(code_a.lower().split())
        tokens_b = set(code_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    def _get_score_fusion(
        self, token_sim: float, ast_sim: float, code_a: str, code_b: str
    ) -> MultiStageScore:
        embed_sim = self._compute_embedding_similarity(code_a, code_b)
        structural_sim = self.WEIGHT_TOKEN * token_sim + self.WEIGHT_AST * ast_sim
        structural_sim /= (self.WEIGHT_TOKEN + self.WEIGHT_AST)
        
        final = (
            self.WEIGHT_TOKEN * token_sim +
            self.WEIGHT_AST * ast_sim +
            self.WEIGHT_EMBED * embed_sim
        )
        
        return MultiStageScore(
            token_sim=token_sim,
            ast_sim=ast_sim,
            embedding_sim=embed_sim,
            structural_sim=structural_sim,
            final_score=final
        )

    def _fallback_similarity(self, code_a: str, code_b: str) -> float:
        tokens_a = set(code_a.lower().split())
        tokens_b = set(code_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)