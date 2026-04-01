"""Decision Engine - Single source of truth for all classification decisions.

Combines engine outputs → applies threshold policy → produces final verdict.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class DecisionResult:
    final_verdict: int       # 0 or 1
    confidence: float        # 0.0-1.0
    threshold_used: float
    policy_applied: str

class DecisionEngine:
    """Centralized decision engine.
    
    Responsibilities:
    1. Merge engine outputs
    2. Apply threshold policy
    3. Produce final verdict
    
    All "is plagiarism?" decisions go through here.
    """
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
    
    def decide(self, score: float) -> DecisionResult:
        """Make binary decision on a single similarity score."""
        verdict = 1 if score >= self.threshold else 0
        # Confidence based on distance from threshold
        dist = abs(score - self.threshold)
        confidence = min(1.0, 0.5 + dist)
        return DecisionResult(
            final_verdict=verdict,
            confidence=confidence,
            threshold_used=self.threshold,
            policy_applied="default_threshold",
        )
    
    def batch_decide(self, scores: List[float]) -> List[DecisionResult]:
        """Batch decision."""
        return [self.decide(s) for s in scores]
