"""Orchestrator Layer - SINGLE entry point for detection workflows."""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from src.core.models import CodePair, FeatureVector, SimilarityScore, EvaluationReport

@dataclass
class DetectionResult:
    """Detection result from orchestrator."""
    predictions: List[Dict[str, Any]]
    metrics: Optional[Dict[str, float]] = None
    report: Optional[Dict] = None

class Orchestrator:
    """
    Single entry point for all detection workflows.
    flow: input → engines → fusion → decision → evaluation → report
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.core.fusion import FusionEngine
        from src.core.decision.threshold import ThresholdPolicy
        from src.evaluation.evaluator import Evaluator
        self.fusion = FusionEngine(weights)
        self.decision = ThresholdPolicy(threshold)
        self.evaluator = Evaluator()
    
    def detect(self, pairs: List[CodePair], code_store: Dict[str, str]) -> DetectionResult:
        """Run full detection pipeline."""
        from src.core.extractor import FeatureExtractor
        extractor = FeatureExtractor()
        feature_vectors = [extractor.extract(pair, code_store.get(pair.a,""), code_store.get(pair.b,"")) for pair in pairs]
        scores = [self.fusion.fuse(fv) for fv in feature_vectors]
        
        predictions = []
        label_map = {p.id: p.label for p in pairs}
        for score in scores:
            pred = self.decision.apply(score.final_score)
            predictions.append({
                "pair_id": score.pair_id,
                "score": score.final_score,
                "predicted": pred,
                "label": label_map.get(score.pair_id, -1),
            })
        return DetectionResult(predictions=predictions)
    
    def detect_and_evaluate(self, pairs: List[CodePair], code_store: Dict[str, str]) -> DetectionResult:
        """Run detection and evaluate results."""
        result = self.detect(pairs, code_store)
        from src.evaluation.evaluator import Evaluator
        preds = [{"pair_id": p["pair_id"], "score": p["score"], "predicted": p["predicted"], "label": p["label"]} for p in result.predictions]
        labeled = [p for p in preds if p["label"] >= 0]
        if labeled:
            eval_result = Evaluator().evaluate([type('P', (), {'pair_id': p['pair_id'],'score': p['score'], 'pred': p['predicted'], 'label': p['label']})() for p in labeled])
            result.metrics = {"precision": eval_result.metrics.precision, "recall": eval_result.metrics.recall, "f1": eval_result.metrics.f1}
        return result
