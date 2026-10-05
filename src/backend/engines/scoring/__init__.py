"""
Scoring Module - Single Source of Truth for Similarity Scores

This module is the ONLY place that computes final similarity scores.
All other modules must be feature providers, not decision makers.

Responsibility: Final similarity score computation, ensemble fusion, threshold application
"""

import logging
import math
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ScoreType(Enum):
    """Types of similarity scores."""

    TOKEN = "token"
    AST = "ast"
    GRAPH = "graph"
    EMBEDDING = "embedding"
    EXECUTION = "execution"
    FUSION = "fusion"


def _unit(value: Any) -> float | None:
    """A finite score clamped to [0, 1], or None when it is not a usable number.

    ``max(0.0, min(1.0, nan))`` is ``1.0``, so a NaN used to be turned into a PERFECT
    score by every clamp in this package. Unusable values are now reported as missing.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return max(0.0, min(1.0, value))


@dataclass
class SimilarityScore:
    """Similarity score with metadata (validated on construction)."""

    value: float  # 0.0 to 1.0
    score_type: ScoreType
    confidence: float  # 0.0 to 1.0
    metadata: dict[str, Any]

    def __post_init__(self):
        """Validate score."""
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.value}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class FusionResult:
    """Result of ensemble fusion."""

    final_score: float
    component_scores: list[SimilarityScore]
    fusion_method: str
    weights: dict[str, float]
    metadata: dict[str, Any]


class ScoreFusionStrategy(ABC):
    """Base class for score fusion strategies."""

    @abstractmethod
    def fuse(self, scores: list[SimilarityScore]) -> FusionResult:
        """Fuse multiple scores into a final score."""


class WeightedAverageFusion(ScoreFusionStrategy):
    """Weighted average fusion strategy."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = dict(
            weights
            or {
                ScoreType.TOKEN.value: 0.2,
                ScoreType.AST.value: 0.3,
                ScoreType.GRAPH.value: 0.25,
                ScoreType.EMBEDDING.value: 0.15,
                ScoreType.EXECUTION.value: 0.1,
            }
        )
        if not all(
            isinstance(w, (int, float)) and not isinstance(w, bool) and math.isfinite(w) and w >= 0
            for w in self.weights.values()
        ):
            raise ValueError("fusion weights must be finite, non-negative numbers")
        if sum(self.weights.values()) <= 0:
            # (was a ZeroDivisionError the first time the weights were normalised)
            raise ValueError("fusion weights must contain at least one positive value")

    def fuse(self, scores: list[SimilarityScore]) -> FusionResult:
        """Fuse scores using weighted average."""
        if not scores:
            raise ValueError("No scores to fuse")

        total_weight = sum(self.weights.values())
        normalized_weights = {k: v / total_weight for k, v in self.weights.items()}

        weighted_sum = 0.0
        total_weight_used = 0.0

        for score in scores:
            weight = normalized_weights.get(score.score_type.value, 0.0)
            weighted_sum += score.value * weight * score.confidence
            total_weight_used += weight * score.confidence

        final_score = weighted_sum / total_weight_used if total_weight_used > 0 else 0.0

        return FusionResult(
            final_score=final_score,
            component_scores=scores,
            fusion_method="weighted_average",
            weights=self.weights,
            metadata={
                "total_weight_used": total_weight_used,
                "num_scores": len(scores),
            },
        )


class MaxConfidenceFusion(ScoreFusionStrategy):
    """Select score with highest confidence."""

    def fuse(self, scores: list[SimilarityScore]) -> FusionResult:
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
            },
        )


_DEFAULT_CONFIDENCE = {
    ScoreType.TOKEN: 0.8,
    ScoreType.AST: 0.9,  # AST is usually reliable
    ScoreType.GRAPH: 0.85,
    ScoreType.EMBEDDING: 0.7,  # embeddings can be noisy
    ScoreType.EXECUTION: 0.95,  # execution is usually accurate
}


class ScoringEngine:
    """
    Single source of truth for similarity scoring.

    This is the ONLY place that computes final similarity scores.
    All other modules must provide features, not make decisions.
    """

    def __init__(self, fusion_strategy: ScoreFusionStrategy | None = None):
        self.fusion_strategy = fusion_strategy or WeightedAverageFusion()
        self._lock = threading.Lock()
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
        token_score: float | None = None,
        ast_score: float | None = None,
        graph_score: float | None = None,
        embedding_score: float | None = None,
        execution_score: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FusionResult:
        """
        Compute final similarity score from component scores.

        This is the SINGLE SOURCE OF TRUTH for similarity scoring. A component that is
        NaN/infinite/non-numeric is left out (and logged) instead of raising or, worse,
        being clamped to 1.0; values a hair outside [0, 1] are clamped.
        """
        inputs = (
            (ScoreType.TOKEN, token_score),
            (ScoreType.AST, ast_score),
            (ScoreType.GRAPH, graph_score),
            (ScoreType.EMBEDDING, embedding_score),
            (ScoreType.EXECUTION, execution_score),
        )
        scores = []
        for score_type, raw in inputs:
            if raw is None:
                continue
            value = _unit(raw)
            if value is None:
                logger.warning("Ignoring unusable %s score: %r", score_type.value, raw)
                continue
            scores.append(
                SimilarityScore(
                    value=value,
                    score_type=score_type,
                    confidence=_DEFAULT_CONFIDENCE[score_type],
                    metadata=dict(metadata or {}),  # one copy per score (was one shared dict)
                )
            )

        if not scores:
            raise ValueError("At least one score must be provided")

        return self.fusion_strategy.fuse(scores)

    def apply_threshold(self, score: float) -> str:
        """Apply threshold to get similarity category."""
        value = _unit(score)
        if value is None:
            return "very_different"
        with self._lock:
            ordered = sorted(self._thresholds.items(), key=lambda x: x[1], reverse=True)
        for category, threshold in ordered:
            if value >= threshold:
                return category
        return "very_different"

    def set_thresholds(self, thresholds: dict[str, float]) -> None:
        """Update thresholds (validated and copied: the caller's dict used to be stored as-is)."""
        if not thresholds:
            raise ValueError("thresholds must not be empty")
        clean: dict[str, float] = {}
        for name, value in thresholds.items():
            checked = _unit(value)
            if checked is None or checked != float(value):  # unusable, or outside [0, 1]
                raise ValueError(f"threshold {name!r} must be a finite number in [0, 1], got {value!r}")
            clean[str(name)] = checked
        with self._lock:
            self._thresholds = clean

    def get_thresholds(self) -> dict[str, float]:
        """Get current thresholds."""
        with self._lock:
            return self._thresholds.copy()


# Global scoring engine instance
_engine: ScoringEngine | None = None
_engine_lock = threading.Lock()


def get_scoring_engine() -> ScoringEngine:
    """Get the global scoring engine (singleton, created once even under concurrency)."""
    global _engine

    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ScoringEngine()

    return _engine


def compute_final_similarity(
    token_score: float | None = None,
    ast_score: float | None = None,
    graph_score: float | None = None,
    embedding_score: float | None = None,
    execution_score: float | None = None,
    metadata: dict[str, Any] | None = None,
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
