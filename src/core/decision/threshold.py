"""Threshold Policy - single threshold application authority."""
from typing import List, Dict, Any

class ThresholdPolicy:
    """Single authority for threshold application."""
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
    def apply(self, score: float) -> int:
        """Apply threshold. score >= threshold → positive."""
        return 1 if score >= self.threshold else 0
    def classify_batch(self, scores: List[float]) -> List[int]:
        return [self.apply(s) for s in scores]
