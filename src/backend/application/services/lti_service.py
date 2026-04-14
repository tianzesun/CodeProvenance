import os
import json
import logging
from typing import Dict, Any, Optional, List
from pylti1p3.contrib.fastapi import FastAPIRequest, FastAPIOIDCLogin, FastAPIMessageLaunch
from pylti1p3.tool_config import ToolConfigJsonFile
from pylti1p3.deep_link_resource import DeepLinkResource

logger = logging.getLogger(__name__)

class LTIService:
    """
    Service for LTI 1.3 integration (Canvas, Moodle, Blackboard).
    Handles OIDC login, launch requests, and grade services.
    Supports LTI Deep Linking and Plagiarism Detection Platform (PDP).
    """
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        if not os.path.exists(config_path):
            with open(config_path, 'w') as f:
                json.dump({}, f)
        self.tool_config = ToolConfigJsonFile(config_path)

    def get_launch_data(self, request: FastAPIRequest) -> Dict[str, Any]:
        """Handle the LTI 1.3 launch request and return user/context data."""
        message_launch = FastAPIMessageLaunch(request, self.tool_config)
        launch_data = message_launch.get_launch_data()
        
        return {
            "user_id": launch_data.get("sub"),
            "course_id": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/context", {}).get("id"),
            "course_title": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/context", {}).get("title"),
            "roles": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/roles", []),
            "assignment_id": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}).get("id"),
            "custom_params": launch_data.get("https://purl.imsglobal.org/spec/lti/claim/custom", {})
        }

    def login(self, request: FastAPIRequest, redirect_url: str):
        """Initiate the OIDC login handshake."""
        oidc_login = FastAPIOIDCLogin(request, self.tool_config)
        return oidc_login.enable_check_cookies().redirect(redirect_url)

    def get_message_launch(self, request: FastAPIRequest) -> FastAPIMessageLaunch:
        """Returns the full message launch object for advanced operations."""
        return FastAPIMessageLaunch(request, self.tool_config)

    def handle_deep_linking(self, request: FastAPIRequest, selection_data: List[Dict[str, Any]]):
        """Respond to an LTI Deep Linking request."""
        message_launch = self.get_message_launch(request)
        deep_link = message_launch.get_deep_link()
        
        resources = []
        for item in selection_data:
            resource = DeepLinkResource()
            resource.set_url(item['url'])
            resource.set_title(item['title'])
            resources.append(resource)
            
        return deep_link.output_response_form(resources)

    def pass_grade(self, request: FastAPIRequest, score: float, comment: Optional[str] = None):
        """Send a grade back to the LMS via AGS."""
        message_launch = self.get_message_launch(request)
        if not message_launch.has_ags():
            logger.warning("LTI Launch does not have AGS support.")
            return False
            
        ags = message_launch.get_ags()
        score_obj = {
            'scoreGiven': score * 100,
            'scoreMaximum': 100,
            'activityProgress': 'Completed',
            'gradingProgress': 'FullyGraded',
            'timestamp': '2026-03-31T12:00:00Z',
            'userId': message_launch.get_launch_data().get('sub')
        }
        if comment:
            score_obj['comment'] = comment
            
        return ags.put_score(score_obj)

    def handle_plagiarism_callback(self, request: FastAPIRequest, submission_id: str, results: Dict[str, Any]):
        """Implement the LTI Plagiarism Detection Platform (PDP) workflow."""
        # PDP uses specific return payloads for the 'Similarity Report' icon in Canvas.
        report_url = f"https://integrity-desk.io/report/{submission_id}"
        
        return {
            "submission_id": submission_id,
            "originality_report_url": report_url,
            "similarity_score": round(results.get("score", 0.0) * 100, 2),
            "ai_probability": round(results.get("ai_probability", 0.0) * 100, 2)
        }
