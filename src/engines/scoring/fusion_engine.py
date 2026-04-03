"""Fusion Engine - Combined multi-engine scoring with configurable weights."""
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class FusedScore:
    """Result of fused multi-engine similarity scoring."""
    final_score: float
    confidence: float = 0.8
    uncertainty: float = 0.0
    agreement_index: float = 1.0
    components: Dict[str, float] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)


# Default weights across all 5 engines
DEFAULT_WEIGHTS: Dict[str, float] = {
    "ast": 0.25,
    "fingerprint": 0.25,
    "embedding": 0.20,
    "ngram": 0.15,
    "winnowing": 0.15,
}


class FusionEngine:
    """Multi-engine fusion scoring authority.

    Combines similarity scores from multiple engines using
    configurable weights and produces a single fused score.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        from src.evaluation.arbitration import BayesianArbitrator
        self.weights: Dict[str, float] = dict(weights or DEFAULT_WEIGHTS)
        # Normalize weights so they sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        self._arbitrator = BayesianArbitrator(engine_prior_precisions={k: v*20 for k, v in self.weights.items()})

    def fuse(self, features: "FeatureVector") -> FusedScore:
        """Combine engine outputs into a single similarity score using Bayesian arbitration.

        Args:
            features: A FeatureVector containing scores from each engine.

        Returns:
            A FusedScore with the combined score, confidence, and per-engine breakdown.
        """
        engine_scores = features.as_dict()
        arbitration = self._arbitrator.arbitrate(engine_scores)

        return FusedScore(
            final_score=arbitration.fused_score,
            confidence=arbitration.agreement_index, # Confidence derived from consensus
            uncertainty=arbitration.uncertainty,
            agreement_index=arbitration.agreement_index,
            components=engine_scores,
            contributions=arbitration.engine_contributions
        )

    def get_weights(self) -> Dict[str, float]:
        """Return the current normalized engine weights."""
        return dict(self.weights)

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Update and re-normalize engine weights.

        Args:
            weights: A dict mapping engine names to raw weight values.
        """
        self.weights = dict(weights)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}