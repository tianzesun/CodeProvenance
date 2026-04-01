"""Detection Service - Thin wrapper (NOT business logic).

Responsibility: Coordinate application layer use cases.
API calls this -> application/use_cases/detect_submission.execute()
"""
from typing import Dict, List, Any, Optional

class DetectionService:
    """Thin service layer - delegates to application use cases."""
    def __init__(self, weights: Optional[Dict] = None, threshold: float = 0.5):
        from src.application.use_cases.detect_submission import DetectSubmission
        self.detect_submission = DetectSubmission(weights, threshold)
    
    def detect(self, submissions: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """Delegate to use case."""
        return self.detect_submission.execute(submissions)
