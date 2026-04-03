from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from src.application.services.lti_service import LTIService
import os
import json

router = APIRouter(prefix="/lti", tags=["LTI"])

# Initialize LTI Service with config file
LTI_CONFIG_PATH = os.getenv("LTI_CONFIG_PATH", "config/lti_config.json")
lti_service = LTIService(LTI_CONFIG_PATH)

@router.get("/login", name="lti_login")
@router.post("/login")
async def lti_login(request: Request):
    """OIDC Login Initiation."""
    redirect_url = str(request.url_for("lti_launch"))
    return lti_service.login(request, redirect_url)

@router.post("/launch", name="lti_launch")
async def lti_launch(request: Request):
    """LTI 1.3 Launch endpoint (Handles PDP and Deep Linking)."""
    try:
        launch_data = lti_service.get_launch_data(request)
        message_launch = lti_service.get_message_launch(request)
        
        # 1. Handle Deep Linking Request (Content Selection)
        if message_launch.is_deep_link_launch():
            # Return a simple UI for picking content
            return HTMLResponse("""
                <h1>IntegrityDesk - Select Content</h1>
                <form action="/api/v1/lti/deep-link-select" method="post">
                    <input type="hidden" name="id" value="pdp_assignment_1">
                    <button type="submit">Enable IntegrityDesk Forensic Scan for this Assignment</button>
                </form>
            """)

        # 2. Handle Standard PDP Launch (Instructor/Student View)
        user_id = launch_data.get("user_id")
        course_id = launch_data.get("course_id")
        return RedirectResponse(url=f"/dashboard?lti_user={user_id}&course={course_id}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"LTI Launch Failed: {str(e)}")

@router.post("/deep-link-select")
async def lti_deep_link_select(request: Request):
    """Handle content selection for Deep Linking."""
    # Mock selection data
    selection = [
        {
            "url": "https://integrity-desk.io/lti/launch",
            "title": "IntegrityDesk Forensic Scan"
        }
    ]
    return lti_service.handle_deep_linking(request, selection)

@router.post("/pdp/callback/{submission_id}")
async def lti_pdp_callback(request: Request, submission_id: str):
    """
    Plagiarism Detection Platform Callback.
    Canvas calls this to get the originality report for a submission.
    """
    # In a real scenario, fetch results from DB
    mock_results = {"score": 0.85, "ai_probability": 0.92}
    pdp_response = lti_service.handle_plagiarism_callback(request, submission_id, mock_results)
    return pdp_response

@router.get("/jwks")
async def get_jwks():
    """Return the Public Key Set (JWKS)."""
    if os.path.exists(LTI_CONFIG_PATH):
        with open(LTI_CONFIG_PATH, 'r') as f:
            config = json.load(f)
            return config.get("jwks", {"keys": []})
    return {"keys": []}
