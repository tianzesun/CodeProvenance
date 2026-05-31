"""Evidence Aggregator - Unified evidence vector from multiple engines.
 
This module implements evidence aggregation WITHOUT scoring:

1. Input: Multiple engine scores (AST, flow, ngram, embedding, etc.)
2. Output: 4-dimension evidence vector (NO scoring)

Evidence Dimensions (FIXED SET):
- structural: control flow + AST + lexical patterns
- lexical: token-level similarity  
- semantic: embedding similarity
- style: stylometry + graph

NO engine scores are averaged or fused here.
All scoring decisions happen in the Rule Engine.

=============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.backend.engines.features.feature_extractor import FeatureVector


@dataclass
class EvidenceVector:
    """Unified evidence vector for decision engine."""

    structural: float  # AST, flow, ngram, winnowing
    lexical: float  # ngram, winnowing, fingerprint
    semantic: float  # embedding
    style: float  # stylometry, graph
    coverage: float = 0.0  # Portion of code covered by matching segments (0.0-1.0)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for policy evaluation."""
        return {
            "structural": self.structural,
            "lexical": self.lexical,
            "semantic": self.semantic,
            "style": self.style,
            "coverage": self.coverage,
        }


def aggregate(features: FeatureVector, logic_flow: float = 0.0) -> EvidenceVector:
    """
    Aggregate all engine outputs into unified evidence vector.

    Args:
        features: FeatureVector from FeatureExtractor
        logic_flow: Pre-computed logic flow similarity

    Returns:
        EvidenceVector with consolidated evidence
    """
    raw_scores = features.as_dict()
    raw_scores["logic_flow"] = logic_flow

    # Structural: control flow + AST + lexical patterns
    structural = max(
        raw_scores.get("ast", 0.0),
        raw_scores.get("logic_flow", 0.0),
        raw_scores.get("ngram", 0.0),
        raw_scores.get("winnowing", 0.0),
    )

    # Lexical: token-level similarity
    lexical = max(
        raw_scores.get("fingerprint", 0.0),
        raw_scores.get("winnowing", 0.0),
        raw_scores.get("ngram", 0.0),
    )

    # Semantic: embedding similarity
    semantic = raw_scores.get("embedding", 0.0)

    # Style: stylometry + graph
    style = max(
        raw_scores.get("graph", 0.0),
        raw_scores.get("stylometry", 0.0),
    )

    return EvidenceVector(
        structural=structural,
        lexical=lexical,
        semantic=semantic,
        style=style,
        coverage=getattr(features, "coverage", 0.0),
    )


def aggregate_from_scores(
    weighted_scores: Dict[str, float], logic_flow: float = 0.0, coverage: float = 0.0
) -> EvidenceVector:
    """
    Aggregate weighted scores into unified evidence vector.

    This version accepts pre-weighted scores instead of raw FeatureVector.
    Used for file-type aware detection where weights have already been applied.

    Args:
        weighted_scores: Dictionary of weighted engine scores
        logic_flow: Pre-computed logic flow similarity
        coverage: Portion of code covered by matching segments (0.0-1.0)

    Returns:
        EvidenceVector with consolidated evidence
    """
    weighted_scores["logic_flow"] = logic_flow

    # Structural: control flow + AST + lexical patterns
    structural = max(
        weighted_scores.get("ast", 0.0),
        weighted_scores.get("logic_flow", 0.0),
        weighted_scores.get("ngram", 0.0),
        weighted_scores.get("winnowing", 0.0),
    )

    # Lexical: token-level similarity
    lexical = max(
        weighted_scores.get("fingerprint", 0.0),
        weighted_scores.get("winnowing", 0.0),
        weighted_scores.get("ngram", 0.0),
    )

    # Semantic: embedding similarity (already weighted)
    semantic = weighted_scores.get("embedding", 0.0)

    # Style: stylometry + graph
    style = max(
        weighted_scores.get("graph", 0.0),
        weighted_scores.get("stylometry", 0.0),
    )

    return EvidenceVector(
        structural=structural,
        lexical=lexical,
        semantic=semantic,
        style=style,
        coverage=coverage,
    )