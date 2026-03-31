"""
Fusion Feature Extractor - EDS.md Layer 2.

Extracts features for fusion model from three engine signals.

Layer 1: Compute S_f, S_a, S_s
Layer 2: Build feature vector (8-12 dims)
Layer 3: Fusion model
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
import math


@dataclass
class EngineSignals:
    """Three engine similarity signals."""
    fingerprint: float    # S_f
    ast: float            # S_a
    semantic: float       # S_s

    def to_dict(self) -> Dict[str, float]:
        return {
            "fingerprint": self.fingerprint,
            "ast": self.ast,
            "semantic": self.semantic,
        }


class FusionFeatureExtractor:
    """
    Extract features for fusion from engine signals.
    
    Base features: [S_f, S_a, S_s]
    Enhanced features:
    - abs(S_f - S_a): disagreement signal
    - abs(S_f - S_s): disagreement signal
    - max(S_f, S_a, S_s): strongest signal
    - min(S_f, S_a, S_s): weakest signal
    - variance(S_f, S_a, S_s): consistency measure
    """
    
    def extract(self, signals: EngineSignals) -> Dict[str, float]:
        """
        Build feature vector from engine signals.
        
        Returns dict with 9 features (names match EDS.md spec).
        """
        sf = signals.fingerprint
        sa = signals.ast
        ss = signals.semantic
        
        features = {
            # Base features (3)
            "S_f": sf,
            "S_a": sa,
            "S_s": ss,
            # Enhanced features: disagreement signals (2)
            "diff_f_a": abs(sf - sa),
            "diff_f_s": abs(sf - ss),
            # Enhanced features: strong/weak signals (2)
            "max_signal": max(sf, sa, ss),
            "min_signal": min(sf, sa, ss),
            # Consistency measure (2)
            "consistency_variance": self._variance([sf, sa, ss]),
        }
        return features
    
    def extract_with_aux(self, signals: EngineSignals, 
                         length_ratio: float = 1.0,
                         token_count_diff: float = 0.0) -> Dict[str, float]:
        """
        Extract features with auxiliary features.
        
        Args:
            signals: Engine signals
            length_ratio: code length ratio
            token_count_diff: token count difference (normalized)
        
        Returns:
            Dict with 11 features.
        """
        features = self.extract(signals)
        features["length_ratio"] = length_ratio
        features["token_count_diff"] = token_count_diff
        return features
    
    @staticmethod
    def _variance(values: list) -> float:
        """Compute variance of signal values."""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)