import json
from typing import Dict, Any, List, Optional
from src.backend.application.services.detection_service import SubmissionAnalyzer
from src.backend.application.services.behavioral_analysis import KeystrokeAnalysisService

class StudentFeedbackService:
    """
    Student-Facing Feedback Portal Service.
    Provides 'pre-submission' similarity alerts and AI probabilities 
    to encourage academic integrity and self-correction.
    """
    
    def __init__(self, analyzer: SubmissionAnalyzer, behavioral_service: KeystrokeAnalysisService):
        self.analyzer = analyzer
        self.behavioral_service = behavioral_service

    def provide_pre_submission_feedback(self, code: str, keystrokes: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Scan a student's draft and provide non-punitive feedback.
        """
        # 1. Similarity Scan against repository/web
        results = self.analyzer.analyze(code)
        
        # 2. Behavioral Check (Keystrokes)
        behavioral_results = {}
        if keystrokes:
            behavioral_results = self.behavioral_service.analyze_session(keystrokes)

        # 3. Formulate Student-Friendly Response
        # We don't show the exact score, but a 'risk level' to encourage review.
        risk_level = "LOW"
        if results.get("score", 0.0) > 0.8:
            risk_level = "CRITICAL"
        elif results.get("score", 0.0) > 0.5:
            risk_level = "HIGH"
        elif results.get("score", 0.0) > 0.3:
            risk_level = "MEDIUM"

        suggestions = []
        if risk_level in ["CRITICAL", "HIGH"]:
            suggestions.append("Your code has a high level of similarity to existing sources. Please ensure you are citing your references or rewrite this section in your own words.")
        
        if behavioral_results.get("is_suspicious"):
            suggestions.append("We detected large blocks of text being pasted. Remember that copying and pasting code without attribution is considered a breach of academic integrity.")

        if results.get("ai_probability", 0.0) > 0.7:
            suggestions.append("The structure of your code is highly similar to AI-generated patterns. We recommend reviewing this section to ensure it reflects your personal coding style.")

        return {
            "risk_status": risk_level,
            "suggestions": suggestions,
            "can_submit": True, # Usually always True, let them submit and be caught if they ignore the warning.
            "timestamp": "2026-04-02T10:00:00Z"
        }

class FeedbackPortalView:
    """
    UI view logic for the student feedback portal.
    """
    
    def render(self, feedback: Dict[str, Any]) -> str:
        # Simplified: in a real system, this would be a React component.
        return f"IntegrityDesk Status: {feedback['risk_status']}. Suggestions: {feedback['suggestions']}"
