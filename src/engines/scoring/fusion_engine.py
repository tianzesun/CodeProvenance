"""Fusion Engine - SINGLE unified scoring implementation."""
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class FusedScore:
    final_score: float
    confidence: float = 0.8
    components: Dict[str, float] = None

class FusionEngine:
    """SINGLE fusion scoring authority."""
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {"ast": 0.35, "fingerprint": 0.40, "embedding": 0.25}
        total = sum(self.weights.values())
        if total > 0: self.weights = {k: v/total for k, v in self.weights.items()}
    
    def fuse(self, features) -> FusedScore:
        """SINGLE responsibility: weighted combination ONLY."""
        final_score = max(0.0, min(1.0,
            self.weights.get("fingerprint", 0) * getattr(features, 'fingerprint', 0) +
            self.weights.get("ast", 0) * getattr(features, 'ast', 0) +
            self.weights.get("embedding", 0) * getattr(features, 'embedding', 0)))
        return FusedScore(final_score=final_score)
