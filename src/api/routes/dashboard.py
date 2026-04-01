"""Dashboard routes for teacher review UI."""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

class SubmissionBatch(BaseModel):
    submissions: Dict[str, str]  # {"filename.py": "code content"}

@router.post("/analyze")
def analyze_batch(req: SubmissionBatch) -> Dict[str, Any]:
    """Analyze all submissions and return sorted case list."""
    from src.application.services.dashboard_service import DashboardService
    service = DashboardService()
    cases = service.analyze_batch(req.submissions)
    summary = service.get_summary(cases)
    return {"summary": summary, "cases": [c.to_dict() for c in cases]}
