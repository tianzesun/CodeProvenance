"""Decision Layer - SINGLE decision authority."""
from src.domain.decision.threshold import ThresholdPolicy
from src.domain.decision.policy import ClassificationPolicy, FinalResult

class DecisionEngine:
    """Single runtime decision authority."""
    def __init__(self, threshold: float = 0.5):
        self.threshold_policy = ThresholdPolicy(threshold)
        self.classification_policy = ClassificationPolicy(threshold)
    def decide(self, fused_score: float, context: dict = None) -> FinalResult:
        return self.classification_policy.decide(fused_score, context)
    def classify(self, score: float) -> int:
        return self.threshold_policy.apply(score)

__all__ = ['DecisionEngine', 'ThresholdPolicy', 'ClassificationPolicy', 'FinalResult']
