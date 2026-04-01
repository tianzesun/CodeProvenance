"""Detection Service - replaces Orchestrator.

Responsibilities:
- call parsers (via engines/parsing/)
- call engines (via engines/features/)
- call scoring (via engines/scoring/)
- call decision (via core/decision/)

NOTHING else.
"""
from typing import Dict, List, Any, Optional

class DetectionService:
    """Single responsibility: coordinate detection pipeline."""
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.engines.features.feature_extractor import FeatureExtractor
        from src.engines.scoring.fusion_engine import FusionEngine
        from src.core.decision import DecisionEngine
        self.extractor = FeatureExtractor()
        self.scoring = FusionEngine(weights)
        self.decision = DecisionEngine(threshold)
    
    def detect(self, submissions: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        submissions: {submission_id: {"code_a": str, "code_b": str}}
        Returns: list of detection results
        """
        results = []
        for sub_id, submission in submissions.items():
            ca, cb = submission.get("code_a", ""), submission.get("code_b", "")
            # Feature extraction
            features = self.extractor.extract(ca, cb)
            # Scoring
            fused = self.scoring.fuse(features)
            # Decision
            final = self.decision.decide(fused.final_score)
            results.append({
                "submission_id": sub_id,
                "score": fused.final_score,
                "decision": final.predicted,
                "confidence": final.confidence,
            })
        return results
