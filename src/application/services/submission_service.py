"""Submission Service - API entry orchestration."""
from typing import Dict, List, Any
from src.application.services.detection_service import SubmissionService as DetSvc

class SubmissionService:
    """Orchestrates submission processing end-to-end."""
    def __init__(self, weights=None, threshold=0.5):
        self.detection = DetSvc(weights, threshold)
    
    def process(self, submissions: Dict[str, Dict[str, str]]) -> List[Dict]:
        return self.detection.detect(submissions)
