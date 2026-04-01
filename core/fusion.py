"""Fusion Engine - Phase 3. Centralize all scoring logic."""
from typing import Dict, Optional
from core.models import FeatureVector, SimilarityScore

class FusionEngine:
    """Compute final similarity score from feature vector."""
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {"ast": 0.35, "fingerprint": 0.40, "ai": 0.25}
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v/total for k, v in self.weights.items()}
    
    def fuse(self, feature_vector: FeatureVector) -> SimilarityScore:
        """
        Compute S_final = weighted combination.
        NO threshold logic here. NO evaluation logic. ONLY scoring.
        """
        s_final = (
            self.weights["fingerprint"] * feature_vector.fingerprint +
            self.weights["ast"] * feature_vector.ast +
            self.weights["ai"] * feature_vector.embedding
        )
        return SimilarityScore(
            pair_id=feature_vector.pair_id,
            features=feature_vector,
            final_score=max(0.0, min(1.0, s_final)),
        )
    
    @classmethod
    def from_config(cls, config_path: str = "config/weights.yaml") -> 'FusionEngine':
        """Load weights from YAML config."""
        import yaml
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            return cls(weights=cfg.get("weights", {}))
        except:
            return cls()
