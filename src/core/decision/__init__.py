"""Decision Layer - SINGLE SOURCE OF TRUTH for all runtime decisions."""
from src.core.decision.threshold import ThresholdPolicy
from src.core.decision.policy import ClassificationPolicy, FinalResult

class DecisionEngine:
    """Single entry point for all final classification decisions."""
    def __init__(self, threshold: float = 0.5):
        self.threshold_policy = ThresholdPolicy(threshold)
        self.classification_policy = ClassificationPolicy(threshold)
    def decide(self, fused_score: float, context: dict = None) -> FinalResult:
        """Single runtime decision authority."""
        return self.classification_policy.decide(fused_score, context)
    def classify(self, score: float) -> int:
        """Simple binary classification."""
        return self.threshold_policy.apply(score)

__all__ = ['DecisionEngine', 'ThresholdPolicy', 'ClassificationPolicy', 'FinalResult']
