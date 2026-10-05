"""API router for Historical Fingerprint endpoints."""

from __future__ import annotations

import functools
import logging
import threading
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.backend.evaluation.historical_fingerprint import (
    HistoricalFingerprintAnalyzer,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/historical-fingerprint", tags=["historical-fingerprint"])

_MAX_CODE_CHARS = 1_000_000
_MAX_QUERY_CODE_CHARS = 100_000  # code in a URL is capped by server/proxy limits anyway
_ID_MAX = 128


class FingerprintRequest(BaseModel):
    """Request body for fingerprint analysis."""

    student_id: str = Field(..., min_length=1, max_length=_ID_MAX)
    code: str = Field(..., max_length=_MAX_CODE_CHARS)
    submission_id: str = Field(..., min_length=1, max_length=_ID_MAX)
    timestamp: str | None = Field(default=None, max_length=64)


class HistoricalAnalysisRequest(BaseModel):
    """Request body for historical analysis."""

    student_id: str = Field(..., min_length=1, max_length=_ID_MAX)
    submission_id: str = Field(..., min_length=1, max_length=_ID_MAX)
    code: str = Field(..., max_length=_MAX_CODE_CHARS)


class CodeRequest(BaseModel):
    """Request body carrying only source code."""

    code: str = Field(..., max_length=_MAX_CODE_CHARS)


# One analyzer for the whole process. A fresh instance per request meant the
# per-student history cache was always empty, so /consistency (which built yet
# another instance) always reported a history count of 0 and a baseline score.
# The lock keeps the shared cache consistent now that handlers run in worker
# threads.
_analyzer_lock = threading.RLock()


@functools.lru_cache(maxsize=1)
def _get_analyzer() -> HistoricalFingerprintAnalyzer:
    return HistoricalFingerprintAnalyzer()


def _failure(action: str) -> HTTPException:
    """Log the active exception; return a generic 500 with a reference id."""
    ref = uuid.uuid4().hex[:12]
    logger.exception("%s failed (ref=%s)", action, ref)
    return HTTPException(status_code=500, detail=f"{action} failed. Reference: {ref}")


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp; a bad value is the caller's error (422), not a 500."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=422, detail="timestamp must be an ISO-8601 date-time"
        ) from None


def _run_analysis(
    student_id: str, code: str, submission_id: str, timestamp: datetime | None
) -> dict[str, Any]:
    try:
        with _analyzer_lock:
            result = _get_analyzer().analyze(
                student_id=student_id,
                code=code,
                submission_id=submission_id,
                timestamp=timestamp,
            )
        return result.to_dict()
    except Exception:
        raise _failure("Fingerprint analysis") from None


# The handlers are plain ``def``: the analysis is CPU-bound, and FastAPI runs
# sync handlers in a worker thread instead of blocking the event loop.


@router.post("/analyze")
def analyze_fingerprint(request: FingerprintRequest) -> dict[str, Any]:
    """
    Analyze a submission against historical patterns.

    Returns:
        FingerprintResult with deviation analysis.
    """
    timestamp = _parse_timestamp(request.timestamp)
    return _run_analysis(request.student_id, request.code, request.submission_id, timestamp)


@router.post("/quick-analyze")
def quick_analyze(
    body: FingerprintRequest | None = None,
    student_id: str | None = Query(
        None, max_length=_ID_MAX, description="Student identifier (deprecated: use JSON body)"
    ),
    code: str | None = Query(
        None,
        max_length=_MAX_QUERY_CODE_CHARS,
        description="Source code (deprecated: use JSON body)",
    ),
    submission_id: str | None = Query(
        None, max_length=_ID_MAX, description="Submission identifier (deprecated: use JSON body)"
    ),
) -> dict[str, Any]:
    """
    Quick fingerprint analysis endpoint.

    Prefer a JSON body. The query-string form is kept for existing clients, but
    source code in a URL is truncated by proxies and ends up in access logs.
    """
    if body is not None:
        student_id, code, submission_id = body.student_id, body.code, body.submission_id
        timestamp = _parse_timestamp(body.timestamp)
    else:
        timestamp = None
    if not (student_id and code and submission_id):
        raise HTTPException(
            status_code=422,
            detail="Provide a JSON body, or student_id, code and submission_id.",
        )
    return _run_analysis(student_id, code, submission_id, timestamp)


@router.get("/consistency/{student_id}")
def get_consistency(
    student_id: str = Path(..., min_length=1, max_length=_ID_MAX),
) -> dict[str, Any]:
    """
    Get historical consistency score for a student.

    Returns:
        Consistency score and history count.
    """
    try:
        with _analyzer_lock:
            analyzer = _get_analyzer()
            consistency = analyzer.get_historical_consistency(student_id)
            historical = getattr(analyzer, "_cache", {}).get(student_id)
            history_count = len(historical.submission_history) if historical else 0
    except Exception:
        raise _failure("Consistency check") from None

    return {
        "student_id": student_id,
        "consistency_score": consistency,
        "history_count": history_count,
    }


def _features_response(code: str) -> dict[str, Any]:
    try:
        with _analyzer_lock:
            features = _get_analyzer().extract_features(code)
    except Exception:
        raise _failure("Feature extraction") from None

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


@router.get("/extract-features")
def extract_features(
    code: str = Query(
        ..., max_length=_MAX_QUERY_CODE_CHARS, description="Source code to analyze"
    ),
) -> dict[str, Any]:
    """Extract style features from code (query form; see the POST variant for large files)."""
    return _features_response(code)


@router.post("/extract-features")
def extract_features_post(body: CodeRequest) -> dict[str, Any]:
    """Extract style features from code supplied in the request body."""
    return _features_response(body.code)
