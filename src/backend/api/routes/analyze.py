"""
Enhanced Analysis API endpoints.

Provides REST API for submitting code for plagiarism analysis,
retrieving results, and managing webhook notifications.

The handlers are plain ``def`` (not ``async def``): they use the synchronous
SQLAlchemy session and write files, and a blocking call inside ``async def``
stalls the whole event loop. FastAPI runs sync handlers in a worker thread.
"""

import hashlib
import ipaddress
import logging
import math
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.middleware.rate_limit import RateLimiter
from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import Job, SimilarityResult, Submission
from src.backend.utils.database import (
    JobService,
    SimilarityResultService,
    SubmissionService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize rate limiter
rate_limiter = RateLimiter()

DEFAULT_THRESHOLD = 0.2
_MAX_SUBMISSIONS = 500
_MAX_SUBMISSION_CHARS = 1_000_000
_MAX_NAME_CHARS = 255
_MAX_WEBHOOK_URL_CHARS = 2048
_UNSAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9._ -]")
_REPORT_FORMATS = "^(html|pdf|json)$"
_BLOCKED_WEBHOOK_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}


# ---------------------------------------------------------------------------
# Validation helpers (pure; no I/O)
# ---------------------------------------------------------------------------


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def parse_threshold(value: Any) -> float:
    """Return a finite threshold in [0, 1].

    It was only converted *after* the job row had been created, so a bad value
    produced a 500 and an orphaned queued job.
    """
    try:
        threshold = float(DEFAULT_THRESHOLD if value is None else value)
    except (TypeError, ValueError):
        raise _bad_request("threshold must be a number between 0.0 and 1.0") from None
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise _bad_request("threshold must be a number between 0.0 and 1.0")
    return threshold


def validate_webhook_url(url: Any) -> str | None:
    """Accept only a public https URL for completion notifications.

    The URL is fetched by the server later, so an unchecked value is a
    server-side request forgery vector (cloud metadata, internal services).
    The component that *sends* the webhook must still re-check what the host
    resolves to; this rejects the obvious cases early.
    """
    if url in (None, ""):
        return None
    if not isinstance(url, str) or len(url) > _MAX_WEBHOOK_URL_CHARS:
        raise _bad_request("webhook_url must be a URL string")
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise _bad_request("webhook_url must be an https URL without credentials")
    if host in _BLOCKED_WEBHOOK_HOSTS or host.endswith((".local", ".internal")):
        raise _bad_request("webhook_url must point to a public host")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url.strip()  # a hostname, not an IP literal
    if not ip.is_global:
        raise _bad_request("webhook_url must point to a public host")
    return url.strip()


def safe_filename(raw_name: str, index: int) -> str:
    """Reduce a client-supplied name to a safe single path component."""
    name = Path(str(raw_name)).name.replace("\\", "_")
    name = _UNSAFE_NAME_CHARS.sub("_", name).strip(" .")[:_MAX_NAME_CHARS]
    return name or f"submission_{index}"


def unique_name(name: str, used: set[str]) -> str:
    """Return ``name`` or ``name_2``, ``name_3``... so no two files collide.

    Two submissions with the same name used to be written to the same file, so
    the second silently overwrote the first while both DB rows pointed at it.
    Comparison is case-insensitive for case-insensitive filesystems.
    """
    candidate, n = name, 1
    path = Path(name)
    while candidate.lower() in used:
        n += 1
        candidate = f"{path.stem}_{n}{path.suffix}"
    used.add(candidate.lower())
    return candidate


def prepare_submissions(raw: Any, allowed_extensions: Any) -> list[dict[str, Any]]:
    """Validate the submission list and decide each file name, before any I/O."""
    if not raw or not isinstance(raw, list):
        raise _bad_request("No submissions provided")
    if len(raw) < 2:
        raise _bad_request("At least 2 submissions required for comparison")
    if len(raw) > _MAX_SUBMISSIONS:
        raise _bad_request(f"At most {_MAX_SUBMISSIONS} submissions are allowed")

    used: set[str] = set()
    prepared: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise _bad_request("Each submission must be an object")
        content = item.get("content", "")
        if not isinstance(content, str):
            raise _bad_request("Submission content must be a string")
        if len(content) > _MAX_SUBMISSION_CHARS:
            raise _bad_request(
                f"Submission {index} exceeds the {_MAX_SUBMISSION_CHARS:,} character limit"
            )
        name = safe_filename(item.get("name") or f"submission_{index}", index)
        if Path(name).suffix.lower() not in allowed_extensions:
            # The pipeline only reads recognized code extensions; default to
            # `.py` (the documented API example language) when unspecified.
            name = f"{name}.py"
        prepared.append(
            {
                "file_name": unique_name(name, used),
                "display_name": str(item.get("name") or name)[:_MAX_NAME_CHARS],
                "content": content,
                "language": item.get("language"),
            }
        )
    return prepared


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/v1/analyze", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED
)
def analyze_submissions(
    request: Request,
    analysis_data: dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Submit code for similarity analysis.

    This is the main endpoint for plagiarism detection. It accepts
    multiple code submissions and returns a job ID for tracking.

    **Request Body:**
    - `name`: Job name (required)
    - `submissions`: List of code submissions (required)
    - `threshold`: Similarity threshold 0.0-1.0 (default: 0.2)
    - `webhook_url`: https URL for completion notification (optional)
    - `options`: Analysis options (optional)

    **Response:**
    - `job_id`: Unique identifier for the analysis job
    - `status`: Job status (pending, processing, completed)
    - `status_url`: URL to check job status
    - `estimated_completion`: Estimated completion time

    **Example Request:**
    ```json
    {
        "name": "CS101 Assignment 3",
        "submissions": [
            {
                "name": "student1_solution.py",
                "content": "def fibonacci(n): ..."
            },
            {
                "name": "student2_solution.py",
                "content": "def fib(n): ..."
            }
        ],
        "threshold": 0.2,
        "webhook_url": "https://example.com/webhook",
        "options": {
            "ai_detection": true,
            "normalize_whitespace": true,
            "strip_comments": false
        }
    }
    ```
    """
    # Extract tenant ID from authenticated API key
    tenant_id = get_current_tenant(request)

    # Rate limit check
    rate_limiter.check_rate_limit(tenant_id, request)

    # Imported lazily to avoid a circular import (server.py mounts this router).
    from src.backend.api.server import (
        ALLOWED_EXTENSIONS,
        REPORTS_DIR,
    )

    # Validate EVERYTHING before touching the database or the disk, so a bad
    # request can no longer leave an orphaned job and half-written files.
    prepared = prepare_submissions(analysis_data.get("submissions"), ALLOWED_EXTENSIONS)
    threshold = parse_threshold(analysis_data.get("threshold"))
    webhook_url = validate_webhook_url(analysis_data.get("webhook_url"))
    options = analysis_data.get("options") or {}
    if not isinstance(options, dict):
        raise _bad_request("options must be an object")
    job_name = str(analysis_data.get("name") or "Unnamed Analysis")[:_MAX_NAME_CHARS]
    assignment_id = analysis_data.get("assignment_id")

    # Set tenant context
    set_tenant_context(db, tenant_id)

    # Create analysis job
    job = JobService.create_job(
        db=db,
        tenant_id=tenant_id,
        name=job_name,
        assignment_id=assignment_id,  # wiring to normalized Assignment
        threshold=threshold,
        webhook_url=webhook_url,
    )

    # Materialize submissions to disk so the shared analysis pipeline
    # (`_run_analysis_background` -> `_run_analysis`) can read them the same
    # way it reads web uploads.
    job_dir = REPORTS_DIR / str(job.id) / "submissions"
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        submission_ids = []
        for item in prepared:
            target = job_dir / item["file_name"]
            target.write_text(item["content"], encoding="utf-8")
            submission = SubmissionService.create_submission(
                db=db,
                job_id=str(job.id),
                name=item["display_name"],
                file_paths=[str(target.relative_to(REPORTS_DIR))],
                language_detected=item["language"],
                storage_path=str(job_dir),
                checksum=hashlib.sha256(item["content"].encode("utf-8")).hexdigest(),
            )
            submission_ids.append(str(submission.id))
    except Exception:
        ref = uuid.uuid4().hex[:12]
        logger.exception("Could not store submissions for job %s (ref=%s)", job.id, ref)
        shutil.rmtree(job_dir.parent, ignore_errors=True)  # no stray student code
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not store the submissions. Reference: {ref}",
        ) from None

    # Queue background processing using the same engine as the upload flow.
    # dispatch_analysis sends the job to Celery when a broker is reachable
    # and runs it in-process otherwise, so the API stays up without Redis.
    from src.backend.workers.dispatch import dispatch_analysis as _dispatch_analysis

    _dispatch_analysis(
        job_id=str(job.id),
        job_dir=job_dir,
        course_name=job_name,
        assignment_name=job_name,
        assignment_id=assignment_id,
        assignment_mode=str(options.get("assignment_mode", "")),
        threshold=threshold,
        current_user=None,
        engine_keys_raw="",
        tool_ids_raw="",
        starter_sources=None,
    )

    # Estimated completion: roughly 2 seconds per pairwise comparison.
    num_submissions = len(prepared)
    num_pairs = num_submissions * (num_submissions - 1) // 2
    estimated_seconds = max(10, num_pairs * 2)
    estimated_completion = (
        datetime.now(timezone.utc) + timedelta(seconds=estimated_seconds)
    ).isoformat()

    return {
        "job_id": str(job.id),
        # Matches the DB-valid initial state set by JobService.create_job.
        "status": "queued",
        "status_url": f"/api/v1/jobs/{job.id}",
        "estimated_completion": estimated_completion,
        "submission_count": num_submissions,
        "submission_ids": submission_ids,
        "message": f"Analysis job created with {num_submissions} submissions",
    }


def _as_float(value: Any) -> float | None:
    """``float(value)`` unless it is None. ``if value`` treated a real 0.0 as missing."""
    return float(value) if value is not None else None


@router.get("/v1/jobs/{job_id}", response_model=dict[str, Any])
def get_job_status(
    job_id: uuid.UUID,
    request: Request,
    include_results: bool = Query(
        True, description="Set false when polling to skip the (large) results list"
    ),
    db: Session = Depends(get_db),
):
    """
    Get analysis job status and results.

    Returns the current status of an analysis job, including
    progress, results, and any errors that occurred.

    **Response:**
    - `job_id`: Job identifier
    - `name`: Job name
    - `status`: Current status (queued, processing, completed, failed)
    - `progress`: Percentage complete (0-100)
    - `submission_count`: Number of submissions
    - `completed_at`: Completion timestamp (if completed)
    - `error_message`: Error details (if failed)
    - `results`: List of similarity results (if completed)
    """
    tenant_id = get_current_tenant(request)
    set_tenant_context(db, tenant_id)

    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    results = []
    if include_results and job.status == "completed":
        similarity_results = SimilarityResultService.get_results_by_job(
            db, str(job_id), threshold=None, limit=1000, offset=0
        )
        results = [
            {
                "id": str(r.id),
                "submission_a_id": str(r.submission_a_id),
                "submission_b_id": str(r.submission_b_id),
                "similarity_score": float(r.similarity_score),
                "confidence_lower": _as_float(r.confidence_lower),
                "confidence_upper": _as_float(r.confidence_upper),
                "detected_clones": r.detected_clones or [],
            }
            for r in similarity_results
        ]

    # Count submissions via a real SQL COUNT — `job.submissions` is a lazy
    # AppenderQuery, which has no len(). The DB column is VARCHAR(36) while
    # the model declares UUID, so cast to avoid `varchar = uuid` errors.
    submission_count = (
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(cast(Submission.job_id, String) == str(job_id))
        )
        or 0
    )

    return {
        "job_id": str(job.id),
        "name": job.name,
        "status": job.status,
        # The Job model has no progress column; derive a coarse value from
        # the status lifecycle instead of reading a non-existent attribute.
        "progress": 100 if job.status == "completed" else 0,
        "submission_count": submission_count,
        "threshold": float(job.threshold),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "results": results,
    }


def _submission_names(db: Session, ids: set[str]) -> dict[str, str]:
    """Names for many submissions in ONE query.

    ``r.submission_a.name`` lazy-loaded two rows per result (``hasattr`` is
    always true), i.e. up to 2,000 extra queries for a 1,000-row page.
    """
    if not ids:
        return {}
    rows = db.execute(
        select(Submission.id, Submission.name).where(cast(Submission.id, String).in_(ids))
    ).all()
    return {str(sid): name for sid, name in rows}


@router.get("/v1/jobs/{job_id}/results", response_model=list[dict[str, Any]])
def get_job_results(
    job_id: uuid.UUID,
    request: Request,
    threshold: float | None = Query(None, ge=0.0, le=1.0),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get detailed similarity results for an analysis job.

    Returns all pairwise similarity comparisons with scores,
    confidence intervals, and matching code blocks.

    **Query Parameters:**
    - `threshold`: Minimum similarity score (0.0-1.0)
    - `limit`: Maximum results to return (default: 1000, max: 5000)
    - `offset`: Pagination offset (default: 0)
    """
    tenant_id = get_current_tenant(request)
    set_tenant_context(db, tenant_id)

    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job {job_id} is not completed (status: {job.status})",
        )

    results = SimilarityResultService.get_results_by_job(
        db, str(job_id), threshold=threshold, limit=limit, offset=offset
    )
    names = _submission_names(
        db, {str(r.submission_a_id) for r in results} | {str(r.submission_b_id) for r in results}
    )

    return [
        {
            "id": str(r.id),
            "submission_a": {
                "id": str(r.submission_a_id),
                "name": names.get(str(r.submission_a_id), "Unknown"),
            },
            "submission_b": {
                "id": str(r.submission_b_id),
                "name": names.get(str(r.submission_b_id), "Unknown"),
            },
            "similarity_score": float(r.similarity_score),
            "confidence_interval": {
                # A real 0.0 bound used to be replaced by the default (and an
                # upper bound of 0.0 by 1.0) because 0.0 is falsy.
                "lower": _as_float(r.confidence_lower) if r.confidence_lower is not None else 0.0,
                "upper": _as_float(r.confidence_upper) if r.confidence_upper is not None else 1.0,
                "confidence": 0.95,
            },
            "detected_clones": r.detected_clones or [],
            "matching_blocks": r.matching_blocks or [],
        }
        for r in results
    ]


@router.get("/v1/jobs/{job_id}/report", response_model=dict[str, Any])
def get_job_report(
    job_id: uuid.UUID,
    request: Request,
    report_format: str = Query("html", alias="format", pattern=_REPORT_FORMATS),
    db: Session = Depends(get_db),
):
    """
    Generate a similarity analysis report.

    Generates a comprehensive report in the specified format
    (HTML, PDF, JSON) for the analysis job.

    **Query Parameters:**
    - `format`: Report format (html, pdf, json) - default: html

    **Response:**
    - `report_url`: URL to download the generated report
    - `format`: Report format
    - `generated_at`: Report generation timestamp
    """
    tenant_id = get_current_tenant(request)
    set_tenant_context(db, tenant_id)

    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job {job_id} is not completed (status: {job.status})",
        )

    # Generate report (placeholder - would integrate with report generator).
    # `format` is validated above, so it can no longer be injected into the URL.
    report_url = f"/api/v1/jobs/{job_id}/report/download?format={report_format}"

    return {
        "job_id": str(job.id),
        "report_url": report_url,
        "format": report_format,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }


@router.get("/v1/usage", response_model=dict[str, Any])
def get_api_usage(request: Request, db: Session = Depends(get_db)):
    """
    Get API usage statistics for the current tenant.

    Returns usage metrics including jobs created, files analyzed,
    API calls made, and rate limit information.
    """
    tenant_id = get_current_tenant(request)
    set_tenant_context(db, tenant_id)

    # One round trip instead of two.
    job_count, result_count = db.execute(
        select(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id).scalar_subquery(),
            select(func.count())
            .select_from(SimilarityResult)
            .where(SimilarityResult.tenant_id == tenant_id)
            .scalar_subquery(),
        )
    ).one()
    job_count, result_count = int(job_count or 0), int(result_count or 0)

    return {
        "tenant_id": tenant_id,
        "jobs_created": job_count,
        "files_analyzed": result_count,
        "api_calls": job_count + result_count,
        "rate_limit": {
            "requests_per_minute": 60,
            "requests_remaining": 60,
            "reset_at": datetime.now(timezone.utc).isoformat(),
        },
    }
