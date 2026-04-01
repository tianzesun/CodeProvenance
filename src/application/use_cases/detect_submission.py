"""Detect Submission Use Case - Single Responsibility.

This is the entry point for the plagiarism detection workflow.
API calls this, Workers call this. NOT engines directly.
"""
from typing import Dict, List, Any, Optional

class DetectSubmission:
    """
    Use Case: Detect code plagiarism between submissions.
    
    flow: submission -> feature extract -> score -> decide
    """
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.engines.features import FeatureExtractor
        from src.engines.scoring import FusionEngine
        from src.domain.decision import DecisionEngine
        
        self.extract_features = FeatureExtractor()
        self.fuse_scores = FusionEngine(weights)
        self.make_decision = DecisionEngine(threshold)
    
    def execute(self, submissions: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Execute detection use case.
        
        Args:
            submissions: {submission_id: {"code_a": str, "code_b": str}}
        Returns:
            List of detection results
        """
        results = []
        for sub_id, submission in submissions.items():
            ca, cb = submission.get("code_a", ""), submission.get("code_b", "")
            
            # Feature Extraction
            features = self.extract_features.extract(ca, cb)
            
            # Fusion Scoring
            fused = self.fuse_scores.fuse(features)
            
            # Decision
            final = self.make_decision.decide(fused.final_score)
            
            results.append({
                "submission_id": sub_id,
                "score": fused.final_score,
                "decision": final.predicted,
                "confidence": final.confidence,
            })
        return results
