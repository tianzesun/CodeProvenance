"""Scoring Pipeline - execution graph only, NO business logic.

Execution flow:
Submission -> Feature Extraction -> Similarity Registry -> Fusion Engine -> Threshold Decision -> Result
"""
from typing import Dict, List, Any, Optional

class ScoringPipeline:
    """
    Formal execution graph.
    This is NOT business logic - it's the execution path definition.
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.engines.features import FeatureExtractor
        from src.engines.scoring import FusionEngine
        from src.core.decision import DecisionEngine
        
        self.feature_extractor = FeatureExtractor()
        self.fusion_engine = FusionEngine(weights)
        self.threshold_engine = DecisionEngine(threshold)
    
    def execute(self, code_a: str, code_b: str, submission_id: str = "") -> Dict[str, Any]:
        """Execute scoring pipeline with full traceability."""
        # Step 1: Feature Extraction
        features = self.feature_extractor.extract(code_a, code_b)
        
        # Step 2: Similarity signals computed in FeatureExtractor
        
        # Step 3: Fusion Scoring
        fused = self.fusion_engine.fuse(features)
        
        # Step 4: Threshold Decision
        decision = self.threshold_engine.decide(fused.final_score)
        
        return {
            "submission_id": submission_id,
            "features": {"ast": features.ast, "fingerprint": features.fingerprint, "embedding": features.embedding},
            "fused_score": fused.final_score,
            "confidence": fused.confidence,
            "decision": decision.predicted,
        }
