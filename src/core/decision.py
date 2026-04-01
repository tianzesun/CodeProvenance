"""Decision - legacy wrapper."""
from src.core.decision.threshold import ThresholdPolicy
from src.core.decision.policy import ClassificationPolicy, FinalResult

ThresholdClassifier = ThresholdPolicy
__all__ = ['ThresholdClassifier', 'ClassificationPolicy', 'FinalResult', 'ThresholdPolicy']
