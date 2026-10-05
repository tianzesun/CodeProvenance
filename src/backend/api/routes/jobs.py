"""
Job management endpoints.
"""

import ipaddress
import logging
import shutil
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.schemas import job as job_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.utils.database import AuditLogService, JobService, SubmissionService

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_WEBHOOK_URL_CHARS = 2048
_BLOCKED_WEBHOOK_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}
_MAX_FILE_PATHS = 1000
_MAX_PATH_CHARS = 1024


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def validate_webhook_url(url: Any) -> str | None:
    """Accept only a public https URL (the server calls it later: SSRF guard).

    The component that sends the webhook must still re-check what the host
    resolves to; this rejects the obvious cases early.
    """
    if url in (None, ""):
        return None
    text = str(url).strip()
    if len(text) > _MAX_WEBHOOK_URL_CHARS:
        raise _bad_request("webhook_url is too long")
    parts = urlsplit(text)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise _bad_request("webhook_url must be an https URL without credentials")
    if host in _BLOCKED_WEBHOOK_HOSTS or host.endswith((".local", ".internal")):
        raise _bad_request("webhook_url must point to a public host")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return text  # a hostname, not an IP literal
    if not ip.is_global:
        raise _bad_request("webhook_url must point to a public host")
    return text


def validate_file_paths(paths: Any) -> Any:
    """Reject absolute paths and ``..`` in client-supplied file paths.

    They are stored and later opened by the analysis pipeline, so an unchecked
    value such as ``/etc/passwd`` or ``../../secrets`` is an arbitrary file read.
    """
    if paths is None:
        return None
    if not isinstance(paths, (list, tuple)) or len(paths) > _MAX_FILE_PATHS:
        raise _bad_request(f"file_paths must be a list of at most {_MAX_FILE_PATHS} paths")
    for raw in paths:
        if not isinstance(raw, str) or not raw or len(raw) > _MAX_PATH_CHARS or "\x00" in raw:
            raise _bad_request("file_paths must be non-empty path strings")
        normalized = raw.replace("\\", "/")
        if (
            PurePosixPath(normalized).is_absolute()
            or PureWindowsPath(raw).is_absolute()
            or ".." in PurePosixPath(normalized).parts
        ):
            raise _bad_request("file_paths must be relative paths without '..'")
    return list(paths)


def _write_audit_log(db: Session, **kwargs: Any) -> None:
    """Write an audit entry without ever failing the request that caused it.

    It used to be queued as a background task that received the *request's*
    session. Since FastAPI 0.106 that session is already closed when background
    tasks run (and the tenant/RLS context is gone), so the log write failed.
    """
    try:
        AuditLogService.create_audit_log(db=db, **kwargs)
    except Exception:
        logger.warning("Audit log write failed: %s", kwargs.get("action"), exc_info=True)
        db.rollback()


def _remove_job_files(job_id: uuid.UUID) -> None:
    """Delete the job's uploaded student code from disk (best effort).

    Deleting the row left the files behind, defeating retention.
    """
    try:
        from src.backend.api.server import REPORTS_DIR

        shutil.rmtree(Path(REPORTS_DIR) / str(job_id), ignore_errors=True)
    except Exception:
        logger.warning("Could not remove files for job %s", job_id, exc_info=True)


# Plain ``def`` handlers: the session is synchronous, so FastAPI runs them in a
# worker thread instead of blocking the event loop.


@router.post(
    "/", response_model=job_schema.JobResponse, status_code=status.HTTP_201_CREATED
)
def create_job(
    request: Request,
    job_data: job_schema.JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new similarity analysis job.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    webhook_url = validate_webhook_url(job_data.webhook_url)

    # Check idempotency key if provided
    if job_data.idempotency_key:
        existing_job = JobService.check_idempotency_key(db, job_data.idempotency_key)
        if existing_job:
            # Never reveal another tenant's job id through the conflict message.
            if str(getattr(existing_job, "tenant_id", tenant_id)) == str(tenant_id):
                detail = (
                    f"Job with idempotency key {job_data.idempotency_key} "
                    f"already exists: {existing_job.id}"
                )
            else:
                detail = "Idempotency key is already in use"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    # Create the job
    job = JobService.create_job(
        db=db,
        tenant_id=tenant_id,
        name=job_data.name,
        assignment_id=job_data.assignment_id,
        threshold=job_data.threshold,
        webhook_url=webhook_url,
        idempotency_key=job_data.idempotency_key,
        detection_modes=job_data.detection_modes,
        language_filters=job_data.language_filters,
        exclude_patterns=job_data.exclude_patterns,
        template_files=job_data.template_files,
        retention_days=job_data.retention_days,
    )

    _write_audit_log(
        db,
        action="job_created",
        tenant_id=tenant_id,
        job_id=str(job.id),
        changes={"name": job_data.name, "threshold": job_data.threshold},
    )

    # In a real implementation, we would enqueue the job for processing
    # background_tasks.add_task(process_job, str(job.id))

    return job


@router.get("/{job_id}", response_model=job_schema.JobResponse)
def get_job(request: Request, job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Get a job by ID.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    return job


@router.get("/", response_model=list[job_schema.JobResponse])
def list_jobs(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str | None = Query(None, alias="status", max_length=32),
    db: Session = Depends(get_db),
):
    """
    List jobs for the current tenant.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    return JobService.get_jobs_by_tenant(
        db, tenant_id, status=status_filter, limit=limit, offset=skip
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(request: Request, job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Delete a job and its stored submission files.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    # Related rows are removed by the ORM cascade.
    db.delete(job)
    db.commit()

    _remove_job_files(job_id)
    # job_id is not passed as a foreign key: the row it would reference is gone.
    _write_audit_log(
        db,
        action="job_deleted",
        tenant_id=tenant_id,
        job_id=None,
        changes={"job_id": str(job_id)},
    )


@router.post("/{job_id}/submit", response_model=job_schema.SubmissionResponse)
def submit_files(
    request: Request,
    job_id: uuid.UUID,
    submission_data: job_schema.SubmissionCreate,
    db: Session = Depends(get_db),
):
    """
    Submit files for a job.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Verify job exists and belongs to tenant
    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    return SubmissionService.create_submission(
        db=db,
        job_id=str(job_id),
        name=submission_data.name,
        file_paths=validate_file_paths(submission_data.file_paths),
        external_id=submission_data.external_id,
    )
