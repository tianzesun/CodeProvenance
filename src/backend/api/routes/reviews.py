"""Pair review endpoints for IntegrityDesk faculty workflow.

Provides:
  POST /api/jobs/{job_id}/reviews          — submit a disposition for a pair
  GET  /api/jobs/{job_id}/reviews          — list current reviews for a job
  GET  /api/jobs/{job_id}/reviews/summary  — aggregate counts (overturn rate etc.)
  GET  /api/jobs/{job_id}/reviews/pair     — history for one specific pair
  GET  /api/jobs/{job_id}/thresholds       — resolved band thresholds for the job

All write operations enforce the AI corroboration rule server-side: if the AI
flag is elevated but not corroborated, high-stakes dispositions (step-up
verification, formal escalation) are rejected with HTTP 422 regardless of what
the frontend sends.

Authentication is handled by the middleware in server.py.  These endpoints
require a logged-in user (``request.state.user`` must be set).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.backend.engines.scoring.review_policy import (
    BandThresholdConfig,
    BAND_THRESHOLDS,
    allowed_dispositions_for_pair,
    compute_band,
    compute_corroboration,
    validate_disposition,
)
from src.backend.infrastructure.db import BandThresholdService, PairReviewService

router = APIRouter()
logger = logging.getLogger(__name__)

_RATIONALE_MAX_CHARS = 500


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ReviewCreate(BaseModel):
    """Request body for submitting a review disposition."""

    submission_a: str = Field(..., min_length=1, max_length=255)
    submission_b: str = Field(..., min_length=1, max_length=255)

    # Policy inputs — used to recompute band / corroboration server-side
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    ai_score: float = Field(default=0.0, ge=0.0, le=1.0)
    assignment_mode: str | None = Field(default=None)
    engine_scores: dict[str, float] | None = Field(default=None)
    web_match_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Faculty decision
    disposition: str = Field(..., min_length=1, max_length=32)
    rationale: str | None = Field(default=None, max_length=_RATIONALE_MAX_CHARS)


class ReviewResponse(BaseModel):
    """Serialised PairReview row returned to the client."""

    id: str
    job_id: str
    submission_a: str
    submission_b: str
    reviewer_id: str
    reviewed_at: datetime
    band: str
    disposition: str
    rationale: str | None
    ai_flag: bool
    corroborated: bool
    corroboration_label: str
    corroboration_reason: str
    similarity_score: float | None
    allowed_dispositions: list[str]
    blocked_dispositions: list[str]
    appeal_status: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewSummaryResponse(BaseModel):
    """Aggregate review counts for a job."""

    job_id: str
    reviewed_total: int
    by_band: dict[str, int]
    by_disposition: dict[str, int]
    overturned: int
    escalated: int
    ai_only_flags: int
    corroborated_flags: int


class ThresholdsResponse(BaseModel):
    """Resolved band thresholds for a job / assignment mode."""

    assignment_mode: str | None
    review_min: float
    high_min: float
    ai_elevated_min: float
    web_match_min: float
    engine_agree_count: int
    engine_agree_min: float
    source: str  # 'db' | 'default'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_user(request: Request) -> dict[str, Any]:
    """Return the authenticated user dict or raise HTTP 401."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _require_job_access(job_id: str, user: dict[str, Any]) -> None:
    """Raise HTTP 404 if the job doesn't exist or is not accessible by *user*.

    Reuses the same access-control logic as the main job endpoints so the
    reviews endpoints enforce the same tenant isolation.  Returns 404 (not
    403) to avoid confirming whether a job exists for an unauthorised caller.
    """
    from src.backend.api.server import _get_job, _job_is_accessible

    job = _get_job(job_id)
    if not job or not _job_is_accessible(job, user):
        raise HTTPException(status_code=404, detail="Job not found.")


def _get_threshold_config(
    db: Session, assignment_mode: str | None
) -> tuple[BandThresholdConfig, str]:
    """Resolve threshold config from DB row or static defaults.

    Returns:
        (BandThresholdConfig, source) where source is ``'db'`` or
        ``'default'``.
    """
    if assignment_mode:
        row = BandThresholdService.get_by_mode(db, assignment_mode)
        if row:
            cfg = BandThresholdConfig(
                review_min=float(row.review_min),
                high_min=float(row.high_min),
                ai_elevated_min=float(row.ai_elevated_min),
                web_match_min=float(row.web_match_min),
                engine_agree_count=int(row.engine_agree_count),
                engine_agree_min=float(row.engine_agree_min),
            )
            return cfg, "db"
    cfg = BandThresholdConfig.from_dict(
        BAND_THRESHOLDS.get((assignment_mode or "").lower(), BAND_THRESHOLDS["default"])
    )
    return cfg, "default"


def _serialise_review(review: Any, cfg: BandThresholdConfig) -> dict[str, Any]:
    """Convert a PairReview ORM row to a response dict.

    Recomputes allowed/blocked dispositions from the stored band, ai_flag, and
    corroborated fields so the client always has up-to-date policy information
    even if thresholds have changed since the review was recorded.
    """
    from src.backend.engines.scoring.review_policy import (
        CorroborationResult,
        HIGH_BAND_DISPOSITIONS,
        HIGH_STAKES_DISPOSITIONS,
        LOW_BAND_DISPOSITIONS,
        REVIEW_BAND_DISPOSITIONS,
    )

    band_map = {
        "low": LOW_BAND_DISPOSITIONS,
        "review": REVIEW_BAND_DISPOSITIONS,
        "high": HIGH_BAND_DISPOSITIONS,
    }
    band_allowed = band_map.get(review.band, LOW_BAND_DISPOSITIONS)

    blocked: frozenset[str] = (
        HIGH_STAKES_DISPOSITIONS if (review.ai_flag and not review.corroborated) else frozenset()
    )
    final_allowed = band_allowed - blocked

    # Reconstruct a lightweight CorroborationResult for label / reason
    if review.ai_flag and not review.corroborated:
        corr_label = "AI-only flag"
        corr_reason = (
            "AI detection was elevated but no corroborating structural or web "
            "evidence was found at review time."
        )
    elif review.ai_flag and review.corroborated:
        corr_label = "AI + similarity"
        corr_reason = "AI detection was elevated and corroborated by structural evidence."
    else:
        corr_label = ""
        corr_reason = ""

    return {
        "id": str(review.id),
        "job_id": review.job_id,
        "submission_a": review.submission_a,
        "submission_b": review.submission_b,
        "reviewer_id": str(review.reviewer_id),
        "reviewed_at": review.reviewed_at,
        "band": review.band,
        "disposition": review.disposition,
        "rationale": review.rationale,
        "ai_flag": bool(review.ai_flag),
        "corroborated": bool(review.corroborated),
        "corroboration_label": corr_label,
        "corroboration_reason": corr_reason,
        "similarity_score": (
            float(review.similarity_score) if review.similarity_score is not None else None
        ),
        "allowed_dispositions": sorted(final_allowed),
        "blocked_dispositions": sorted(blocked),
        "appeal_status": review.appeal_status,
        "created_at": review.created_at,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/jobs/{job_id}/reviews", status_code=201)
async def create_review(
    job_id: str,
    payload: ReviewCreate,
    request: Request,
) -> dict[str, Any]:
    """Submit a faculty disposition for a flagged submission pair.

    The server recomputes the band and corroboration state from the supplied
    scores and enforces the AI corroboration rule regardless of what the client
    sends.  If the requested disposition is blocked, the endpoint returns HTTP
    422 with a clear explanation.

    Returns the newly created review row.
    """
    user = _require_user(request)
    reviewer_id: str = user["id"]
    _require_job_access(job_id, user)

    from src.backend.api.server import SessionLocal

    with SessionLocal() as db:
        # Resolve thresholds (DB row wins over static defaults)
        cfg, _source = _get_threshold_config(db, payload.assignment_mode)

        # Recompute band and corroboration server-side
        band_result = compute_band(
            payload.similarity_score,
            threshold_override=cfg,
        )
        corr_result = compute_corroboration(
            ai_score=payload.ai_score,
            similarity_score=payload.similarity_score,
            engine_scores=payload.engine_scores,
            web_match_score=payload.web_match_score,
            threshold_override=cfg,
        )

        # Enforce the AI corroboration rule
        ok, reason = validate_disposition(payload.disposition, band_result, corr_result)
        if not ok:
            raise HTTPException(status_code=422, detail=reason)

        # Enforce rationale length (Pydantic max_length covers it, but be safe)
        rationale = payload.rationale
        if rationale:
            rationale = rationale.strip()[:_RATIONALE_MAX_CHARS] or None

        review = PairReviewService.create_review(
            db=db,
            job_id=job_id,
            submission_a=payload.submission_a,
            submission_b=payload.submission_b,
            reviewer_id=reviewer_id,
            band=band_result.band,
            disposition=payload.disposition,
            rationale=rationale,
            ai_flag=corr_result.ai_flag,
            corroborated=corr_result.corroborated,
            similarity_score=payload.similarity_score,
        )

        logger.info(
            "Review created: job=%s pair=(%s, %s) band=%s disposition=%s reviewer=%s",
            job_id,
            payload.submission_a,
            payload.submission_b,
            band_result.band,
            payload.disposition,
            reviewer_id,
        )

        return _serialise_review(review, cfg)


@router.get("/api/jobs/{job_id}/reviews")
async def list_reviews(
    job_id: str,
    request: Request,
    band: str | None = Query(default=None, description="Filter by band: low | review | high"),
    disposition: str | None = Query(default=None, description="Filter by disposition"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Return the latest review for each reviewed pair in *job_id*.

    Optionally filter by ``band`` or ``disposition``.  Unreviewed pairs are
    not included — use the job results endpoint to get all pairs, then cross-
    reference by (submission_a, submission_b) to find pending ones.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

    from src.backend.api.server import SessionLocal

    with SessionLocal() as db:
        cfg, _ = _get_threshold_config(db, None)
        reviews = PairReviewService.get_latest_for_job(
            db,
            job_id=job_id,
            band=band,
            disposition=disposition,
            limit=limit,
            offset=offset,
        )
        return {
            "job_id": job_id,
            "count": len(reviews),
            "reviews": [_serialise_review(r, cfg) for r in reviews],
        }


@router.get("/api/jobs/{job_id}/reviews/summary")
async def get_review_summary(
    job_id: str,
    request: Request,
) -> ReviewSummaryResponse:
    """Return aggregate review counts for *job_id*.

    Includes per-band and per-disposition counts, overturn count, escalation
    count, and AI flag breakdown — all computed over the latest review per pair.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

    from src.backend.api.server import SessionLocal

    with SessionLocal() as db:
        summary = PairReviewService.get_review_summary(db, job_id=job_id)
        return ReviewSummaryResponse(**summary)


@router.get("/api/jobs/{job_id}/reviews/pair")
async def get_pair_review_history(
    job_id: str,
    request: Request,
    submission_a: str = Query(..., description="First submission name"),
    submission_b: str = Query(..., description="Second submission name"),
) -> dict[str, Any]:
    """Return the full review history for one specific pair (newest first).

    Useful for the disposition panel to show prior decisions and rationale
    before the reviewer makes a new one.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

    from src.backend.api.server import SessionLocal

    with SessionLocal() as db:
        cfg, _ = _get_threshold_config(db, None)
        history = PairReviewService.get_history_for_pair(
            db,
            job_id=job_id,
            submission_a=submission_a,
            submission_b=submission_b,
        )
        return {
            "job_id": job_id,
            "submission_a": submission_a,
            "submission_b": submission_b,
            "count": len(history),
            "history": [_serialise_review(r, cfg) for r in history],
        }


@router.get("/api/jobs/{job_id}/thresholds")
async def get_job_thresholds(
    job_id: str,
    request: Request,
    assignment_mode: str | None = Query(
        default=None,
        description="Assignment mode to resolve thresholds for (default: 'default')",
    ),
) -> ThresholdsResponse:
    """Return the resolved band threshold config for a given assignment mode.

    The frontend uses this to display the correct band boundaries and to
    pre-compute which dispositions are available before the reviewer submits.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

    from src.backend.api.server import SessionLocal

    with SessionLocal() as db:
        cfg, source = _get_threshold_config(db, assignment_mode)
        return ThresholdsResponse(
            assignment_mode=assignment_mode,
            review_min=cfg.review_min,
            high_min=cfg.high_min,
            ai_elevated_min=cfg.ai_elevated_min,
            web_match_min=cfg.web_match_min,
            engine_agree_count=cfg.engine_agree_count,
            engine_agree_min=cfg.engine_agree_min,
            source=source,
        )
