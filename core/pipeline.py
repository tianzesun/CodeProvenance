"""Pipeline Orchestrator - Phase 6. Single entry point."""
from typing import List, Dict, Optional
from core.models import CodePair, FeatureVector, SimilarityScore, Prediction, EvaluationReport
from core.extractor import FeatureExtractor
from core.fusion import FusionEngine
from core.decision import ThresholdClassifier
from core.evaluator import Evaluator

class EvalPipeline:
    """Orchestrate full evaluation pipeline."""
    
    def __init__(self, weights: Optional[Dict[str, float]] = None, threshold: float = 0.5):
        self.extractor = FeatureExtractor()
        self.fusion = FusionEngine(weights)
        self.classifier = ThresholdClassifier(threshold)
        self.evaluator = Evaluator()
    
    def run(self, pairs: List[CodePair], code_store: Dict[str, str]) -> EvaluationReport:
        """
        flow: pairs → features → fusion → classify → evaluate
        """
        # Extract features
        feature_vectors = []
        for pair in pairs:
            fv = self.extractor.extract(pair, code_store.get(pair.a, ""), code_store.get(pair.b, ""))
            feature_vectors.append(fv)
        
        # Fusion (compute S_final)
        scores = [self.fusion.fuse(fv) for fv in feature_vectors]
        
        # Classification (threshold)
        predictions = self.classifier.predict(scores)
        
        # Set labels from pairs
        label_map = {p.id: p.label for p in pairs}
        for pred in predictions:
            if pred.pair_id in label_map:
                pred.label = label_map[pred.pair_id]
        
        # Evaluate
        return self.evaluator.evaluate(predictions)
