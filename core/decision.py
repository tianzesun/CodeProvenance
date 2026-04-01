"""Decision Layer - Phase 4. Threshold and classification logic."""
from typing import List, Tuple
from core.models import SimilarityScore, Prediction

class ThresholdClassifier:
    """Apply threshold to similarity scores."""
    
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
    
    def predict(self, scores: List[SimilarityScore]) -> List[Prediction]:
        """Apply threshold. Single responsibility: classification only."""
        predictions = []
        for score in scores:
            pred = Prediction(
                pair_id=score.pair_id,
                score=score.final_score,
                pred=1 if score.final_score >= self.threshold else 0,
            )
            predictions.append(pred)
        return predictions
    
    def classify(self, score: float) -> int:
        """Single score classification."""
        return 1 if score >= self.threshold else 0
