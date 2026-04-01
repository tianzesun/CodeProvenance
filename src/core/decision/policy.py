"""Classification Policy - unified final decision authority."""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class FinalResult:
    predicted: int
    confidence: float
    score: float
    details: Dict[str, Any]

class ClassificationPolicy:
    """Single authority for all final classification decisions."""
    def __init__(self, threshold: float = 0.5, min_confidence: float = 0.5):
        self.threshold = threshold
        self.min_confidence = min_confidence
    def decide(self, score: float, context: Optional[Dict] = None) -> FinalResult:
        """Single final decision authority."""
        predicted = 1 if score >= self.threshold else 0
        confidence = max(abs(score - 0.5) * 2, 0.5)  # Simple confidence mapping
        return FinalResult(predicted=predicted, confidence=confidence, score=score, details=context or {})
