"""Orchestrator - SINGLE entry point for ALL detection workflows.

DESIGN RULE: This module is RUNTIME ONLY.
- NEVER import evaluation/ here (evaluation is OFFLINE only)
- ALL decision logic MUST go through core/decision/
- Pipeline MUST call orchestrator, not engines directly
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from src.core.models import CodePair, FeatureVector

@dataclass
class DetectionResult:
    """Result from orchestrator - decision from SINGLE decision layer."""
    pair_id: str
    score: float
    decision: int  # 0 or 1 from DecisionEngine ONLY
    confidence: float

class Orchestrator:
    """
    SINGLE entry point for all detection workflows.
    flow: input → engines → fusion → DECISION (single source) → result
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.core.fusion import FusionEngine
        from src.core.decision import DecisionEngine
        self.fusion = FusionEngine(weights)
        self.decision = DecisionEngine(threshold)
    
    def run(self, pairs: List[CodePair], code_store: Dict[str, str]) -> List[DetectionResult]:
        """Run detection through orchestrator ONLY."""
        from src.core.extractor import FeatureExtractor
        extractor = FeatureExtractor()
        feature_vectors = [extractor.extract(pair, code_store.get(pair.a,""), code_store.get(pair.b,"")) for pair in pairs]
        results = []
        for pair, fv in zip(pairs, feature_vectors):
            fused_score = self.fusion.fuse(fv)
            final = self.decision.decide(fused_score.final_score)
            results.append(DetectionResult(
                pair_id=pair.id,
                score=fused_score.final_score,
                decision=final.predicted,
                confidence=final.confidence,
            ))
        return results
