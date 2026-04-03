"""
Scoring Module - Single Source of Truth for Similarity Scores

This module is the ONLY place that computes final similarity scores.
All other modules must be feature providers, not decision makers.

Responsibility: Final similarity score computation, ensemble fusion, threshold application
"""

from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import numpy as np


class ScoreType(Enum):
    """Types of similarity scores."""
    TOKEN = "token"
    AST = "ast"
    GRAPH = "graph"
    EMBEDDING = "embedding"
    EXECUTION = "execution"
    FUSION = "fusion"


@dataclass
class SimilarityScore:
    """Immutable similarity score with metadata."""
    value: float  # 0.0 to 1.0
    score_type: ScoreType
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate score."""
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.value}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class FusionResult:
    """Result of ensemble fusion."""
    final_score: float
    component_scores: List[SimilarityScore]
    fusion_method: str
    weights: Dict[str, float]
    metadata: Dict[str, Any]


class ScoreFusionStrategy(ABC):
    """Base class for score fusion strategies."""
    
    @abstractmethod
    def fuse(self, scores: List[SimilarityScore]) -> FusionResult:
        """Fuse multiple scores into a final score."""
        pass


class WeightedAverageFusion(ScoreFusionStrategy):
    """Weighted average fusion strategy."""
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            ScoreType.TOKEN.value: 0.2,
            ScoreType.AST.value: 0.3,
            ScoreType.GRAPH.value: 0.25,
            ScoreType.EMBEDDING.value: 0.15,
            ScoreType.EXECUTION.value: 0.1,
        }
    
    def fuse(self, scores: List[SimilarityScore]) -> FusionResult:
        """Fuse scores using weighted average."""
        if not scores:
            raise ValueError("No scores to fuse")
        
        # Normalize weights
        total_weight = sum(self.weights.values())
        normalized_weights = {k: v / total_weight for k, v in self.weights.items()}
        
        # Calculate weighted average
        weighted_sum = 0.0
        total_weight_used = 0.0
        
        for score in scores:
            weight = normalized_weights.get(score.score_type.value, 0.0)
            weighted_sum += score.value * weight * score.confidence
            total_weight_used += weight * score.confidence
        
        if total_weight_used == 0:
            final_score = 0.0
        else:
            final_score = weighted_sum / total_weight_used
        
        return FusionResult(
            final_score=final_score,
            component_scores=scores,
            fusion_method="weighted_average",
            weights=self.weights,
            metadata={
                "total_weight_used": total_weight_used,
                "num_scores": len(scores),
            }
        )


class MaxConfidenceFusion(ScoreFusionStrategy):
    """Select score with highest confidence."""
    
    def fuse(self, scores: List[SimilarityScore]) -> FusionResult:
        """Select score with highest confidence."""
        if not scores:
            raise ValueError("No scores to fuse")
        
        best_score = max(scores, key=lambda s: s.confidence)
        
        return FusionResult(
            final_score=best_score.value,
            component_scores=scores,
            fusion_method="max_confidence",
            weights={best_score.score_type.value: 1.0},
            metadata={
                "selected_score_type": best_score.score_type.value,
                "confidence": best_score.confidence,
            }
        )


class ScoringEngine:
    """
    Single source of truth for similarity scoring.
    
    This is the ONLY place that computes final similarity scores.
    All other modules must provide features, not make decisions.
    """
    
    def __init__(self, fusion_strategy: Optional[ScoreFusionStrategy] = None):
        self.fusion_strategy = fusion_strategy or WeightedAverageFusion()
        self._thresholds = {
            "identical": 1.0,
            "very_similar": 0.9,
            "similar": 0.7,
            "somewhat_similar": 0.5,
            "different": 0.3,
            "very_different": 0.0,
        }
    
    def compute_similarity(
        self,
        token_score: Optional[float] = None,
        ast_score: Optional[float] = None,
        graph_score: Optional[float] = None,
        embedding_score: Optional[float] = None,
        execution_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FusionResult:
        """
        Compute final similarity score from component scores.
        
        This is the SINGLE SOURCE OF TRUTH for similarity scoring.
        """
        scores = []
        
        if token_score is not None:
            scores.append(SimilarityScore(
                value=token_score,
                score_type=ScoreType.TOKEN,
                confidence=0.8,  # Default confidence
                metadata=metadata or {}
            ))
        
        if ast_score is not None:
            scores.append(SimilarityScore(
                value=ast_score,
                score_type=ScoreType.AST,
                confidence=0.9,  # AST is usually reliable
                metadata=metadata or {}
            ))
        
        if graph_score is not None:
            scores.append(SimilarityScore(
                value=graph_score,
                score_type=ScoreType.GRAPH,
                confidence=0.85,
                metadata=metadata or {}
            ))
        
        if embedding_score is not None:
            scores.append(SimilarityScore(
                value=embedding_score,
                score_type=ScoreType.EMBEDDING,
                confidence=0.7,  # Embeddings can be noisy
                metadata=metadata or {}
            ))
        
        if execution_score is not None:
            scores.append(SimilarityScore(
                value=execution_score,
                score_type=ScoreType.EXECUTION,
                confidence=0.95,  # Execution is usually accurate
                metadata=metadata or {}
            ))
        
        if not scores:
            raise ValueError("At least one score must be provided")
        
        return self.fusion_strategy.fuse(scores)
    
    def apply_threshold(self, score: float) -> str:
        """Apply threshold to get similarity category."""
        for category, threshold in sorted(
            self._thresholds.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if score >= threshold:
                return category
        return "very_different"
    
    def set_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update thresholds."""
        self._thresholds = thresholds
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get current thresholds."""
        return self._thresholds.copy()


# Global scoring engine instance
_engine: Optional[ScoringEngine] = None


def get_scoring_engine() -> ScoringEngine:
    """Get the global scoring engine (singleton)."""
    global _engine
    
    if _engine is None:
        _engine = ScoringEngine()
    
    return _engine


def compute_final_similarity(
    token_score: Optional[float] = None,
    ast_score: Optional[float] = None,
    graph_score: Optional[float] = None,
    embedding_score: Optional[float] = None,
    execution_score: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> FusionResult:
    """
    Compute final similarity score.
    
    This is the SINGLE ENTRY POINT for similarity scoring.
    All other code must call this function, not compute scores directly.
    """
    engine = get_scoring_engine()
    return engine.compute_similarity(
        token_score=token_score,
        ast_score=ast_score,
        graph_score=graph_score,
        embedding_score=embedding_score,
        execution_score=execution_score,
        metadata=metadata,
    )