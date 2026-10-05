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

The handlers are plain ``def`` (not ``async def``) because they do blocking
database work; FastAPI runs them in a worker thread so they cannot stall the
event loop.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from src.backend.config.database import get_db
from src.backend.engines.scoring.review_policy import (
    BAND_THRESHOLDS,
    HIGH_BAND_DISPOSITIONS,
    HIGH_STAKES_DISPOSITIONS,
    LOW_BAND_DISPOSITIONS,
    REVIEW_BAND_DISPOSITIONS,
    BandThresholdConfig,
    compute_band,
    compute_corroboration,
    validate_disposition,
)
from src.backend.infrastructure.db import BandThresholdService, PairReviewService

router = APIRouter()
logger = logging.getLogger(__name__)

_RATIONALE_MAX_CHARS = 500
_MAX_ENGINE_SCORES = 32

_BAND_DISPOSITIONS = {
    "low": LOW_BAND_DISPOSITIONS,
    "review": REVIEW_BAND_DISPOSITIONS,
    "high": HIGH_BAND_DISPOSITIONS,
}


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
    assignment_mode: str | None = Field(default=None, max_length=64)
    engine_scores: dict[str, float] | None = Field(default=None)
    web_match_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Faculty decision
    disposition: str = Field(..., min_length=1, max_length=32)
    rationale: str | None = Field(default=None, max_length=_RATIONALE_MAX_CHARS)

    @field_validator("engine_scores")
    @classmethod
    def _engine_scores_sane(
        cls, value: dict[str, float] | None
    ) -> dict[str, float] | None:
        """Bound the dict and keep every score in [0, 1] like the other scores."""
        if value is None:
            return None
        if len(value) > _MAX_ENGINE_SCORES:
            raise ValueError(f"At most {_MAX_ENGINE_SCORES} engine scores allowed")
        for name, score in value.items():
            if len(name) > 64 or not 0.0 <= score <= 1.0:
                raise ValueError("Engine scores must be named and between 0 and 1")
        return value

    @model_validator(mode="after")
    def _distinct_submissions(self) -> ReviewCreate:
        if self.submission_a.strip() == self.submission_b.strip():
            raise ValueError("A pair must contain two different submissions")
        return self


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
    if not user or not user.get("id"):
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

    The mode is looked up as given and then case-normalised, so the DB and the
    static table agree (the static table was already lower-cased, the DB lookup
    was not, which made ``"Exam"`` and ``"exam"`` resolve differently).

    Returns:
        (BandThresholdConfig, source) where source is ``'db'`` or
        ``'default'``.
    """
    mode = (assignment_mode or "").strip()
    normalised = mode.lower()
    if mode:
        row = BandThresholdService.get_by_mode(db, mode)
        if row is None and normalised != mode:
            row = BandThresholdService.get_by_mode(db, normalised)
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
        BAND_THRESHOLDS.get(normalised, BAND_THRESHOLDS["default"])
    )
    return cfg, "default"


def _serialise_review(
    review: Any, cfg: BandThresholdConfig | None = None
) -> dict[str, Any]:
    """Convert a PairReview ORM row to a response dict.

    Recomputes allowed/blocked dispositions from the stored band, ai_flag, and
    corroborated fields, so the client always has current policy information.
    The result depends only on the stored row, not on any threshold config;
    ``cfg`` is accepted for backward compatibility and ignored.
    """
    band_allowed = _BAND_DISPOSITIONS.get(review.band, LOW_BAND_DISPOSITIONS)

    blocked: frozenset[str] = (
        HIGH_STAKES_DISPOSITIONS
        if (review.ai_flag and not review.corroborated)
        else frozenset()
    )
    final_allowed = band_allowed - blocked

    if review.ai_flag and not review.corroborated:
        corr_label = "AI-only flag"
        corr_reason = (
            "AI detection was elevated but no corroborating structural or web "
            "evidence was found at review time."
        )
    elif review.ai_flag and review.corroborated:
        corr_label = "AI + similarity"
        corr_reason = (
            "AI detection was elevated and corroborated by structural evidence."
        )
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
            float(review.similarity_score)
            if review.similarity_score is not None
            else None
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
def create_review(
    job_id: str,
    payload: ReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submit a faculty disposition for a flagged submission pair.

    The server recomputes the band and corroboration state from the supplied
    scores and enforces the AI corroboration rule regardless of what the client
    sends.  If the requested disposition is blocked, the endpoint returns HTTP
    422 with a clear explanation.

    Returns the newly created review row.
    """
    user = _require_user(request)
    reviewer_id = str(user["id"])
    _require_job_access(job_id, user)

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

    rationale = payload.rationale
    if rationale:
        rationale = rationale.strip()[:_RATIONALE_MAX_CHARS] or None

    try:
        review = PairReviewService.create_review(
            db=db,
            job_id=job_id,
            submission_a=payload.submission_a.strip(),
            submission_b=payload.submission_b.strip(),
            reviewer_id=reviewer_id,
            band=band_result.band,
            disposition=payload.disposition,
            rationale=rationale,
            ai_flag=corr_result.ai_flag,
            corroborated=corr_result.corroborated,
            similarity_score=payload.similarity_score,
        )
    except Exception:
        # Generic message to the client; details (which may include SQL or
        # student file names) stay in the log under the reference id.
        ref = uuid.uuid4().hex[:12]
        logger.exception("Saving review failed (job=%s ref=%s)", job_id, ref)
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Could not save the review. Reference: {ref}"
        ) from None

    # Submission names can identify students, so they are left out of the log.
    logger.info(
        "Review created: job=%s band=%s disposition=%s reviewer=%s",
        job_id,
        band_result.band,
        payload.disposition,
        reviewer_id,
    )

    return _serialise_review(review)


@router.get("/api/jobs/{job_id}/reviews")
def list_reviews(
    job_id: str,
    request: Request,
    band: str | None = Query(
        default=None,
        pattern="^(low|review|high)$",
        description="Filter by band: low | review | high",
    ),
    disposition: str | None = Query(
        default=None, max_length=32, description="Filter by disposition"
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the latest review for each reviewed pair in *job_id*.

    Optionally filter by ``band`` or ``disposition``.  Unreviewed pairs are
    not included — use the job results endpoint to get all pairs, then cross-
    reference by (submission_a, submission_b) to find pending ones.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

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
        "reviews": [_serialise_review(r) for r in reviews],
    }


@router.get("/api/jobs/{job_id}/reviews/summary")
def get_review_summary(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ReviewSummaryResponse:
    """Return aggregate review counts for *job_id*.

    Includes per-band and per-disposition counts, overturn count, escalation
    count, and AI flag breakdown — all computed over the latest review per pair.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

    summary = PairReviewService.get_review_summary(db, job_id=job_id)
    return ReviewSummaryResponse(**summary)


@router.get("/api/jobs/{job_id}/reviews/pair")
def get_pair_review_history(
    job_id: str,
    request: Request,
    submission_a: str = Query(..., max_length=255, description="First submission name"),
    submission_b: str = Query(
        ..., max_length=255, description="Second submission name"
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the full review history for one specific pair (newest first).

    Useful for the disposition panel to show prior decisions and rationale
    before the reviewer makes a new one.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

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
        "history": [_serialise_review(r) for r in history],
    }


@router.get("/api/jobs/{job_id}/thresholds")
def get_job_thresholds(
    job_id: str,
    request: Request,
    assignment_mode: str | None = Query(
        default=None,
        max_length=64,
        description="Assignment mode to resolve thresholds for (default: 'default')",
    ),
    db: Session = Depends(get_db),
) -> ThresholdsResponse:
    """Return the resolved band threshold config for a given assignment mode.

    The frontend uses this to display the correct band boundaries and to
    pre-compute which dispositions are available before the reviewer submits.
    """
    user = _require_user(request)
    _require_job_access(job_id, user)

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
