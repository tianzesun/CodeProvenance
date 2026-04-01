"""Orchestrator Layer - SINGLE entry point for detection workflows."""
from typing import Dict, List, Any, Optional
from src.core.models import CodePair, FeatureVector, SimilarityScore, EvaluationReport

class Orchestrator:
    """
    Single entry point for all detection workflows.
    flow: input → engines → fusion → evaluation → report
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.core.fusion import FusionEngine
        from src.core.evaluator import Evaluator
        from src.core.decision import ThresholdClassifier
        self.fusion = FusionEngine(weights)
        self.classifier = ThresholdClassifier(threshold)
        self.evaluator = Evaluator()
    def detect(self, pairs: List[CodePair], code_store: Dict[str, str]) -> EvaluationReport:
        """Run full detection pipeline."""
        from src.core.extractor import FeatureExtractor
        extractor = FeatureExtractor()
        feature_vectors = [extractor.extract(pair, code_store.get(pair.a,""), code_store.get(pair.b,"")) for pair in pairs]
        scores = [self.fusion.fuse(fv) for fv in feature_vectors]
        predictions = self.classifier.predict(scores)
        label_map = {p.id: p.label for p in pairs}
        for pred in predictions:
            if pred.pair_id in label_map:
                pred.label = label_map[pred.pair_id]
        return self.evaluator.evaluate(predictions)
