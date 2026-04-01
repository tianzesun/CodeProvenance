"""Detection Service - SINGLE entry point for detection workflows."""
from typing import Dict, List, Any, Optional

class DetectionService:
    """
    SINGLE entry point for all detection workflows.
    flow: submission -> feature extract -> scoring -> decision
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.engines.features.feature_extractor import FeatureExtractor as _FE
        from src.engines.scoring.fusion_engine import FusionEngine as _Fusion
        from src.core.decision import DecisionEngine
        self.extractor = _FE()
        self.scoring = _Fusion(weights)
        self.decision = DecisionEngine(threshold)
    
    def detect(self, submissions: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """Run detection. NEVER call engines directly."""
        results = []
        for sub_id, submission in submissions.items():
            ca, cb = submission.get("code_a", ""), submission.get("code_b", "")
            features = self.extractor.extract(ca, cb)
            fused = self.scoring.fuse(features)
            final = self.decision.decide(fused.final_score)
            results.append({
                "submission_id": sub_id,
                "score": fused.final_score,
                "decision": final.predicted,
                "confidence": final.confidence,
            })
        return results
