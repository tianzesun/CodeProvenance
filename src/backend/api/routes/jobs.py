"""
Job management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import Job, Submission
from src.backend.utils.database import JobService, SubmissionService, AuditLogService
from src.backend.api.schemas import job as job_schema

router = APIRouter()

@router.post("/", response_model=job_schema.JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: job_schema.JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a new similarity analysis job.
    """
    # In a real implementation, we would extract tenant_id from API key
    # For now, we'll use a placeholder - this should come from authentication
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Check idempotency key if provided
    if job_data.idempotency_key:
        existing_job = JobService.check_idempotency_key(db, job_data.idempotency_key)
        if existing_job:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job with idempotency key {job_data.idempotency_key} already exists: {existing_job.id}"
            )
    
    # Create the job
    job = JobService.create_job(
        db=db,
        tenant_id=tenant_id,
        name=job_data.name,
        threshold=job_data.threshold,
        webhook_url=job_data.webhook_url,
        idempotency_key=job_data.idempotency_key,
        detection_modes=job_data.detection_modes,
        language_filters=job_data.language_filters,
        exclude_patterns=job_data.exclude_patterns,
        template_files=job_data.template_files,
        retention_days=job_data.retention_days
    )
    
    # Log the job creation
    background_tasks.add_task(
        AuditLogService.create_audit_log,
        db=db,
        action="job_created",
        tenant_id=tenant_id,
        job_id=str(job.id),
        changes={"name": job_data.name, "threshold": job_data.threshold}
    )
    
    # In a real implementation, we would enqueue the job for processing
    # background_tasks.add_task(process_job, str(job.id))
    
    return job

@router.get("/{job_id}", response_model=job_schema.JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Get a job by ID.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return job

@router.get("/", response_model=List[job_schema.JobResponse])
async def list_jobs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List jobs for the current tenant.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    jobs = JobService.get_jobs_by_tenant(db, tenant_id, status=status, limit=limit, offset=skip)
    return jobs

@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Delete a job.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # In a real implementation, we would also delete associated data
    # For now, we'll just delete the job (cascade will handle related data)
    db.delete(job)
    db.commit()
    
    # Log the deletion
    # background_tasks.add_task(
    #     AuditLogService.create_audit_log,
    #     db=db,
    #     action="job_deleted",
    #     tenant_id=tenant_id,
    #     job_id=str(job_id),
    #     changes={}
    # )
    
    return None

@router.post("/{job_id}/submit", response_model=job_schema.SubmissionResponse)
async def submit_files(
    job_id: uuid.UUID,
    submission_data: job_schema.SubmissionCreate,
    db: Session = Depends(get_db)
):
    """
    Submit files for a job.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Verify job exists and belongs to tenant
    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Create submission
    submission = SubmissionService.create_submission(
        db=db,
        job_id=str(job_id),
        name=submission_data.name,
        file_paths=submission_data.file_paths,
        external_id=submission_data.external_id
    )
    
    return submission
