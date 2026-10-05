"""
Submission management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.schemas import submission as submission_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import Submission
from src.backend.utils.database import JobService, SubmissionService

router = APIRouter()


def _require_job(db: Session, job_id: uuid.UUID, tenant_id) -> None:
    """404 unless the job exists and belongs to the tenant."""
    if not JobService.get_job_by_id(db, str(job_id), tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )


# Plain ``def`` handlers: the session is synchronous, so FastAPI runs them in a
# worker thread instead of blocking the event loop.


@router.get("/", response_model=list[submission_schema.SubmissionResponse])
def list_submissions(
    request: Request,
    job_id: uuid.UUID,
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List submissions for a job.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # This used to skip the ownership check and "rely on RLS" (see the removed
    # TODO); verify it explicitly, as get_submission already did.
    _require_job(db, job_id, tenant_id)

    submissions = SubmissionService.get_submissions_by_job(db, str(job_id))
    return submissions[offset : offset + limit]


@router.get("/{submission_id}", response_model=submission_schema.SubmissionResponse)
def get_submission(
    request: Request,
    submission_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get a specific submission by ID within a job."""
    tenant_id = get_current_tenant(request)
    set_tenant_context(db, str(tenant_id))

    _require_job(db, job_id, tenant_id)

    # The ``submissions`` id columns are VARCHAR(36) while the model declares
    # UUID (see the same note in analyze.py); casting avoids `varchar = uuid`
    # errors from comparing the column directly with a string.
    submission = (
        db.query(Submission)
        .filter(
            cast(Submission.id, String) == str(submission_id),
            cast(Submission.job_id, String) == str(job_id),
        )
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


# Create/update/delete submissions are not implemented here; creation lives in
# jobs.py as a nested endpoint under jobs.
