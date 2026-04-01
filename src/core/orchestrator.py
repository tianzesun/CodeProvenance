"""Orchestrator - ONLY entry point for ALL detection workflows.

Design rules:
- pipeline MUST call orchestrator, not engines directly
- evaluation is offline ONLY, never affects runtime
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from src.core.models import CodePair, FeatureVector, SimilarityScore

@dataclass
class DetectionResult:
    pair_id: str
    score: float
    decision: int  # 0 or 1 from SINGLE decision layer
    confidence: float

class Orchestrator:
    """
    ONLY entry point for all detection workflows.
    flow: input → engines → fusion → DECISION → result
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.core.fusion import FusionEngine
        from src.core.decision import DecisionEngine
        self.fusion = FusionEngine(weights)
        self.decision_engine = DecisionEngine(threshold)
    
    def run(self, pairs: List[CodePair], code_store: Dict[str, str]) -> List[DetectionResult]:
        """Run detection through orchestrator ONLY."""
        from src.core.extractor import FeatureExtractor
        extractor = FeatureExtractor()
        feature_vectors = [extractor.extract(pair, code_store.get(pair.a,""), code_store.get(pair.b,"")) for pair in pairs]
        results = []
        for pair, fv in zip(pairs, feature_vectors):
            score = self.fusion.fuse(fv)
            final = self.decision_engine.decide(score.final_score, {"pair_id": pair.id})
            results.append(DetectionResult(
                pair_id=pair.id,
                score=score.final_score,
                decision=final.predicted,
                confidence=final.confidence,
            ))
        return results
