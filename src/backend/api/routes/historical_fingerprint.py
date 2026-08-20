"""API router for Historical Fingerprint endpoints."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.backend.evaluation.historical_fingerprint import (
    HistoricalFingerprintAnalyzer,
    run_fingerprint_analysis,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/historical-fingerprint", tags=["historical-fingerprint"]
)


class FingerprintRequest(BaseModel):
    """Request body for fingerprint analysis."""

    student_id: str
    code: str
    submission_id: str
    timestamp: str | None = None


class HistoricalAnalysisRequest(BaseModel):
    """Request body for historical analysis."""

    student_id: str
    submission_id: str
    code: str


@router.post("/analyze")
async def analyze_fingerprint(
    request: FingerprintRequest,
) -> dict[str, Any]:
    """
    Analyze a submission against historical patterns.

    Args:
        request: Fingerprint analysis request.

    Returns:
        FingerprintResult with deviation analysis.
    """
    try:
        timestamp = None
        if request.timestamp:
            timestamp = datetime.fromisoformat(request.timestamp)

        analyzer = HistoricalFingerprintAnalyzer()
        result = analyzer.analyze(
            student_id=request.student_id,
            code=request.code,
            submission_id=request.submission_id,
            timestamp=timestamp,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Fingerprint analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-analyze")
async def quick_analyze(
    student_id: str = Query(..., description="Student identifier"),
    code: str = Query(..., description="Source code to analyze"),
    submission_id: str = Query(..., description="Submission identifier"),
) -> dict[str, Any]:
    """
    Quick fingerprint analysis endpoint.

    Args:
        student_id: Student identifier.
        code: Source code to analyze.
        submission_id: Submission identifier.

    Returns:
        FingerprintResult with analysis.
    """
    try:
        result = run_fingerprint_analysis(
            student_id=student_id,
            code=code,
            submission_id=submission_id,
        )
        return result.to_dict()

    except Exception as e:
        logger.error(f"Quick fingerprint analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consistency/{student_id}")
async def get_consistency(
    student_id: str,
) -> dict[str, Any]:
    """
    Get historical consistency score for a student.

    Args:
        student_id: Student identifier.

    Returns:
        Consistency score and history count.
    """
    try:
        analyzer = HistoricalFingerprintAnalyzer()
        consistency = analyzer.get_historical_consistency(student_id)

        historical = analyzer._cache.get(student_id)
        history_count = len(historical.submission_history) if historical else 0

        return {
            "student_id": student_id,
            "consistency_score": consistency,
            "history_count": history_count,
        }

    except Exception as e:
        logger.error(f"Consistency check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/extract-features")
async def extract_features(
    code: str = Query(..., description="Source code to analyze"),
) -> dict[str, Any]:
    """
    Extract style features from code.

    Args:
        code: Source code to analyze.

    Returns:
        Extracted style features.
    """
    try:
        analyzer = HistoricalFingerprintAnalyzer()
        features = analyzer.extract_features(code)

        return {
            "avg_line_length": features.avg_line_length,
            "max_line_length": features.max_line_length,
            "indentation_depth": features.indentation_depth,
            "comment_ratio": features.comment_ratio,
            "blank_line_ratio": features.blank_line_ratio,
            "naming_convention": features.naming_convention,
            "function_count": features.function_count,
            "class_count": features.class_count,
            "complexity_score": features.complexity_score,
            "token_count": features.token_count,
            "hash": features.hash,
        }

    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
