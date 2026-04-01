"""Submission Detection Service.

Orchestrates: feature extraction → scoring → decision.
"""
from typing import Dict, List, Any, Optional
from src.domain.decision import DecisionEngine

class SubmissionService:
    """Application service for code submission detection."""
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.engines.features.feature_extractor import FeatureExtractor
        from src.engines.scoring.fusion_engine import FusionEngine
        self.feature_extractor = FeatureExtractor()
        self.fusion_engine = FusionEngine(weights)
        self.decision = DecisionEngine(threshold)
    
    def detect(self, submissions: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """Run detection on submissions."""
        results = []
        for sub_id, submission in submissions.items():
            ca, cb = submission.get("code_a", ""), submission.get("code_b", "")
            features = self.feature_extractor.extract(ca, cb)
            fused = self.fusion_engine.fuse(features)
            final = self.decision.decide(fused.final_score)
            results.append({
                "submission_id": sub_id, "score": fused.final_score,
                "decision": final.predicted, "confidence": final.confidence})
        return results
