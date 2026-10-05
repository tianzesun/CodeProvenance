"""API router for Evidence Viewer endpoints."""

from __future__ import annotations

import functools
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.backend.evaluation.evidence_viewer import (
    EvidenceViewer,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence-view", tags=["evidence-view"])

_MAX_CODE_CHARS = 500_000
_MAX_QUERY_CODE_CHARS = 20_000  # URL length limits make larger query values unusable
_MAX_ENGINES = 64


class EvidenceViewRequest(BaseModel):
    """Request body for evidence view generation."""

    code_a: str = Field(..., max_length=_MAX_CODE_CHARS)
    code_b: str = Field(..., max_length=_MAX_CODE_CHARS)
    submission_a_id: str = Field(..., min_length=1, max_length=128)
    submission_b_id: str = Field(..., min_length=1, max_length=128)
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    engine_details: dict[str, float] | None = Field(default=None, max_length=_MAX_ENGINES)


class DiffRequest(BaseModel):
    """Request body for a diff of two submissions."""

    code_a: str = Field(..., max_length=_MAX_CODE_CHARS)
    code_b: str = Field(..., max_length=_MAX_CODE_CHARS)


#: Static, so built once rather than on every request.
_VERDICT_OPTIONS: dict[str, Any] = {
    "verdicts": [
        {"value": "HIGH_RISK", "description": "High risk of plagiarism"},
        {"value": "MEDIUM_RISK", "description": "Medium risk, manual review needed"},
        {"value": "LOW_RISK", "description": "Low risk of plagiarism"},
        {"value": "INCONCLUSIVE", "description": "Insufficient evidence"},
    ]
}


@functools.lru_cache(maxsize=1)
def _get_viewer() -> EvidenceViewer:
    """Shared viewer; it was rebuilt on every request."""
    return EvidenceViewer()


def _failure(action: str) -> HTTPException:
    """Log the active exception; return a generic 500 with a reference id."""
    ref = uuid.uuid4().hex[:12]
    logger.exception("%s failed (ref=%s)", action, ref)
    return HTTPException(status_code=500, detail=f"{action} failed. Reference: {ref}")


# Plain ``def`` handlers: diffing and matching are CPU-bound, so FastAPI runs
# them in a worker thread instead of stalling the event loop.


@router.post("/generate")
def generate_evidence_view_endpoint(request: EvidenceViewRequest) -> dict[str, Any]:
    """
    Generate an evidence view for a code pair.

    Returns:
        Evidence view with matched elements and diff analysis.
    """
    try:
        result = _get_viewer().generate_view(
            code_a=request.code_a,
            code_b=request.code_b,
            submission_a_id=request.submission_a_id,
            submission_b_id=request.submission_b_id,
            similarity_score=request.similarity_score,
            engine_details=request.engine_details,
        )
        return result.to_dict()
    except Exception:
        raise _failure("Evidence view generation") from None


@router.post("/diff")
def get_diff(
    body: DiffRequest | None = None,
    code_a: str | None = Query(
        None,
        max_length=_MAX_QUERY_CODE_CHARS,
        description="First code submission (deprecated: use JSON body)",
    ),
    code_b: str | None = Query(
        None,
        max_length=_MAX_QUERY_CODE_CHARS,
        description="Second code submission (deprecated: use JSON body)",
    ),
) -> dict[str, Any]:
    """
    Get a diff between two code submissions.

    Send the code in a JSON body. The query-string form is kept for existing
    clients, but real files exceed URL length limits (so it failed for anything
    but tiny snippets) and the code ends up in access logs.
    """
    if body is not None:
        code_a, code_b = body.code_a, body.code_b
    if code_a is None or code_b is None:
        raise HTTPException(status_code=422, detail="Provide code_a and code_b.")

    try:
        hunks = _get_viewer()._generate_diff(code_a, code_b)
        return {
            "diff_hunks": [
                {
                    "hunk_type": h.hunk_type,
                    "line_number": h.line_number,
                    "content": h.content,
                    "original_content": h.original_content,
                }
                for h in hunks
            ]
        }
    except Exception:
        raise _failure("Diff generation") from None


@router.get("/verdict-options")
async def get_verdict_options() -> dict[str, Any]:
    """
    Get available verdict options.

    Returns:
        List of possible verdicts.
    """
    return _VERDICT_OPTIONS
