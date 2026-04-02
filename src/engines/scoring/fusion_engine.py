"""Fusion Engine - Combined multi-engine scoring with configurable weights."""
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class FusedScore:
    """Result of fused multi-engine similarity scoring."""
    final_score: float
    confidence: float = 0.8
    components: Dict[str, float] = field(default_factory=dict)


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
        self.weights: Dict[str, float] = dict(weights or DEFAULT_WEIGHTS)
        # Normalize weights so they sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def fuse(self, features: "FeatureVector") -> FusedScore:
        """Combine engine outputs into a single similarity score.

        Args:
            features: A FeatureVector containing scores from each engine.

        Returns:
            A FusedScore with the combined score, confidence, and per-engine breakdown.
        """
        score = 0.0
        components: Dict[str, float] = {}

        engine_names = ["ast", "fingerprint", "embedding", "ngram", "winnowing"]
        for engine in engine_names:
            weight = self.weights.get(engine, 0.0)
            value = getattr(features, engine, 0.0)
            score += weight * value
            components[engine] = round(value, 4)

        # Clamp final score to [0, 1]
        final_score = round(max(0.0, min(1.0, score)), 4)

        # Simple confidence model: higher when more engines agree
        non_zero = sum(1 for v in components.values() if v > 0.0)
        total_engines = len([w for w in self.weights.values() if w > 0.0])
        confidence = round(non_zero / max(total_engines, 1), 4) if total_engines else 0.0

        return FusedScore(
            final_score=final_score,
            confidence=confidence,
            components=components,
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