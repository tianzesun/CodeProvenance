"""
Submission management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import Submission
from src.backend.utils.database import SubmissionService, AuditLogService
from src.backend.api.schemas import submission as submission_schema

router = APIRouter()

@router.get("/", response_model=List[submission_schema.SubmissionResponse])
async def list_submissions(
    job_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    List submissions for a job.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Verify job exists and belongs to tenant (we would need a job service method for this)
    # For now, we'll just get submissions by job_id and rely on RLS to filter by tenant via job
    submissions = SubmissionService.get_submissions_by_job(db, str(job_id))
    return submissions

@router.get("/{submission_id}", response_model=submission_schema.SubmissionResponse)
async def get_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Get a submission by ID.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # We would need a method to get submission by id with tenant check
    # For now, we'll get all submissions for a job and filter? This is inefficient.
    # We need to add a method in SubmissionService to get by id with job_id and then check job's tenant.
    # Let's assume we have a method: SubmissionService.get_submission_by_id(db, submission_id, job_id)
    # But we don't have that yet. We'll create a simple version for now.
    
    # Since we don't have a direct method, we'll do a workaround: get all submissions for all jobs? Not good.
    # Instead, we'll change the approach: we'll require job_id to be provided as a query param or we'll get it from the submission.
    # But the endpoint is /submissions/{submission_id}, so we don't have job_id.
    
    # We need to adjust our design: either we add a method to get submission by id and then check the job's tenant,
    # or we change the API to require job_id in the path: /jobs/{job_id}/submissions/{submission_id}
    # Let's change the API to be nested under jobs for better security and clarity.
    
    # However, to keep moving, we'll implement a simple version that gets the submission and then checks the job's tenant.
    # We'll need to get the job_id from the submission, then get the job, then check the tenant.
    
    # For now, we'll return a placeholder and note that this needs improvement.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented yet"
    )

# We'll leave the other endpoints (create, update, delete) for later as they are less critical for the MVP.
# The create submission endpoint is already in jobs.py as a nested endpoint under jobs.
