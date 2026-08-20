"""API router for Evidence Viewer endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.backend.evaluation.evidence_viewer import (
    EvidenceViewer,
    generate_evidence_view,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence-view", tags=["evidence-view"])


class EvidenceViewRequest(BaseModel):
    """Request body for evidence view generation."""

    code_a: str
    code_b: str
    submission_a_id: str
    submission_b_id: str
    similarity_score: float
    engine_details: Optional[Dict[str, float]] = None


@router.post("/generate")
async def generate_evidence_view_endpoint(
    request: EvidenceViewRequest,
) -> Dict[str, Any]:
    """
    Generate an evidence view for a code pair.

    Args:
        request: Evidence view request with code and metadata.

    Returns:
        Evidence view with matched elements and diff analysis.
    """
    try:
        viewer = EvidenceViewer()
        result = viewer.generate_view(
            code_a=request.code_a,
            code_b=request.code_b,
            submission_a_id=request.submission_a_id,
            submission_b_id=request.submission_b_id,
            similarity_score=request.similarity_score,
            engine_details=request.engine_details,
        )
        return result.to_dict()

    except Exception as e:
        logger.error(f"Evidence view generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diff")
async def get_diff(
    code_a: str = Query(..., description="First code submission"),
    code_b: str = Query(..., description="Second code submission"),
) -> Dict[str, Any]:
    """
    Get a diff between two code submissions.

    Args:
        code_a: First code submission.
        code_b: Second code submission.

    Returns:
        Diff hunks showing changes.
    """
    try:
        viewer = EvidenceViewer()
        from src.backend.evaluation.evidence_viewer import DiffHunk

        hunks = viewer._generate_diff(code_a, code_b)

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

    except Exception as e:
        logger.error(f"Diff generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verdict-options")
async def get_verdict_options() -> Dict[str, Any]:
    """
    Get available verdict options.

    Returns:
        List of possible verdicts.
    """
    return {
        "verdicts": [
            {"value": "HIGH_RISK", "description": "High risk of plagiarism"},
            {
                "value": "MEDIUM_RISK",
                "description": "Medium risk, manual review needed",
            },
            {"value": "LOW_RISK", "description": "Low risk of plagiarism"},
            {"value": "INCONCLUSIVE", "description": "Insufficient evidence"},
        ]
    }
