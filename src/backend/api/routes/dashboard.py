"""Dashboard routes for teacher review UI."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_MAX_FILES = 500
_MAX_NAME_CHARS = 255
_MAX_FILE_CHARS = 1_000_000
_MAX_TOTAL_CHARS = 20_000_000


class SubmissionBatch(BaseModel):
    # {"filename.py": "code content"}. Analysis is superlinear in the number of
    # files, so the batch is bounded instead of accepting any size.
    submissions: dict[str, str] = Field(..., min_length=1, max_length=_MAX_FILES)

    @field_validator("submissions")
    @classmethod
    def _within_limits(cls, files: dict[str, str]) -> dict[str, str]:
        total = 0
        for name, content in files.items():
            if not name.strip() or len(name) > _MAX_NAME_CHARS:
                raise ValueError("File names must be 1-%d characters" % _MAX_NAME_CHARS)
            if len(content) > _MAX_FILE_CHARS:
                raise ValueError("A file exceeds the %d character limit" % _MAX_FILE_CHARS)
            total += len(content)
        if total > _MAX_TOTAL_CHARS:
            raise ValueError("The batch exceeds the %d character limit" % _MAX_TOTAL_CHARS)
        return files


# Plain ``def``: analysis is CPU-bound, so FastAPI runs it in a worker thread.
@router.post("/analyze")
def analyze_batch(req: SubmissionBatch) -> dict[str, Any]:
    """Analyze all submissions and return sorted case list."""
    from src.backend.application.services.dashboard_service import DashboardService

    try:
        # A new service per request on purpose: nothing from one instructor's
        # batch can leak into another's through shared state.
        service = DashboardService()
        cases = service.analyze_batch(req.submissions)
        summary = service.get_summary(cases)
        return {"summary": summary, "cases": [c.to_dict() for c in cases]}
    except Exception:
        ref = uuid.uuid4().hex[:12]
        logger.exception("Dashboard analysis failed (ref=%s)", ref)
        raise HTTPException(
            status_code=500, detail=f"Analysis failed. Reference: {ref}"
        ) from None
