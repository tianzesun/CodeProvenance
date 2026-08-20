"""
Submission management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.schemas import submission as submission_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import Submission
from src.backend.utils.database import SubmissionService

router = APIRouter()


@router.get("/", response_model=list[submission_schema.SubmissionResponse])
async def list_submissions(
    request: Request, job_id: uuid.UUID, db: Session = Depends(get_db)
):
    """
    List submissions for a job.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Verify job exists and belongs to tenant (we would need a job service method for this)
    # For now, we'll just get submissions by job_id and rely on RLS to filter by tenant via job
    submissions = SubmissionService.get_submissions_by_job(db, str(job_id))
    return submissions


@router.get("/{submission_id}", response_model=submission_schema.SubmissionResponse)
async def get_submission(
    request: Request,
    submission_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get a specific submission by ID within a job."""
    tenant_id = get_current_tenant(request)
    set_tenant_context(db, str(tenant_id))

    # Verify job belongs to tenant
    from src.backend.utils.database import JobService

    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    submission = (
        db.query(Submission)
        .filter(
            Submission.id == str(submission_id),
            Submission.job_id == str(job_id),
        )
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


# We'll leave the other endpoints (create, update, delete) for later as they are less critical for the MVP.
# The create submission endpoint is already in jobs.py as a nested endpoint under jobs.
