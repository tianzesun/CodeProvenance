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


# Baseline scores expected for two unrelated files in the same language.
# These represent the "noise floor" — scores that occur just from sharing
# a language's syntax, common patterns, and embedding vocabulary.
# Scores at or below baseline are treated as zero similarity.
LANGUAGE_BASELINE: Dict[str, float] = {
    "embedding": 0.70,    # UniXcoder sees "this is Python code" for both
    "winnowing": 0.15,    # Common keywords/structures produce some overlap
    "ngram": 0.05,        # Character n-grams share syntax tokens
    "ast": 0.05,          # Similar AST node types (functions, returns, etc.)
    "fingerprint": 0.05,  # Token-level overlap from language keywords
}


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

    Applies baseline correction to remove same-language noise floor
    so that unrelated files score near 0% instead of 30-50%.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        from src.evaluation.arbitration import BayesianArbitrator
        self.weights: Dict[str, float] = dict(weights or DEFAULT_WEIGHTS)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        self._arbitrator = BayesianArbitrator(engine_prior_precisions={k: v*20 for k, v in self.weights.items()})

    def fuse(self, features: "FeatureVector") -> FusedScore:
        """Combine engine outputs into a single similarity score using Bayesian arbitration.

        Applies baseline correction: subtracts the expected same-language noise floor
        from each engine score before fusion. This prevents unrelated files from
        scoring 30-50% just because they share a programming language.

        Args:
            features: A FeatureVector containing scores from each engine.

        Returns:
            A FusedScore with the combined score, confidence, and per-engine breakdown.
        """
        raw_scores = features.as_dict()

        # Apply baseline correction — subtract noise floor from each engine
        corrected_scores = {}
        for name, score in raw_scores.items():
            baseline = LANGUAGE_BASELINE.get(name, 0.0)
            corrected = max(0.0, score - baseline) / max(0.01, 1.0 - baseline)
            corrected_scores[name] = round(corrected, 4)

        arbitration = self._arbitrator.arbitrate(corrected_scores)

        return FusedScore(
            final_score=arbitration.fused_score,
            confidence=arbitration.agreement_index,
            uncertainty=arbitration.uncertainty,
            agreement_index=arbitration.agreement_index,
            components=raw_scores,
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
        self._arbitrator = BayesianArbitrator(engine_prior_precisions={k: v*20 for k, v in self.weights.items()})

    def fuse(self, features: "FeatureVector") -> FusedScore:
        """Combine engine outputs into a single similarity score using Bayesian arbitration.

        Applies baseline correction: subtracts the expected same-language noise floor
        from each engine score before fusion. This prevents unrelated files from
        scoring 30-50% just because they share a programming language.

        Args:
            features: A FeatureVector containing scores from each engine.

        Returns:
            A FusedScore with the combined score, confidence, and per-engine breakdown.
        """
        raw_scores = features.as_dict()

        # Apply baseline correction — subtract noise floor from each engine
        corrected_scores = {}
        for name, score in raw_scores.items():
            baseline = LANGUAGE_BASELINE.get(name, 0.0)
            corrected = max(0.0, score - baseline) / max(0.01, 1.0 - baseline)
            corrected_scores[name] = round(corrected, 4)

        arbitration = self._arbitrator.arbitrate(corrected_scores)

        return FusedScore(
            final_score=arbitration.fused_score,
            confidence=arbitration.agreement_index,
            uncertainty=arbitration.uncertainty,
            agreement_index=arbitration.agreement_index,
            components=raw_scores,
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