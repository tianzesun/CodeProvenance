"""Dashboard routes for teacher review UI."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SubmissionBatch(BaseModel):
    submissions: dict[str, str]  # {"filename.py": "code content"}


@router.post("/analyze")
def analyze_batch(req: SubmissionBatch) -> dict[str, Any]:
    """Analyze all submissions and return sorted case list."""
    from src.backend.application.services.dashboard_service import DashboardService

    service = DashboardService()
    cases = service.analyze_batch(req.submissions)
    summary = service.get_summary(cases)
    return {"summary": summary, "cases": [c.to_dict() for c in cases]}
