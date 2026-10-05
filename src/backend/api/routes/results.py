"""
Similarity results endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.schemas import result as result_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.utils.database import JobService, SimilarityResultService

router = APIRouter()


# Plain ``def``: the session is synchronous, so FastAPI runs this in a worker
# thread instead of blocking the event loop.
@router.get("/{job_id}", response_model=list[result_schema.ResultResponse])
def get_job_results(
    request: Request,
    job_id: uuid.UUID,
    threshold: float | None = Query(None, ge=0.0, le=1.0),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get similarity results for a job.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Verify the job belongs to the tenant rather than relying on RLS alone.
    if not JobService.get_job_by_id(db, str(job_id), tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    return SimilarityResultService.get_results_by_job(
        db=db, job_id=str(job_id), threshold=threshold, limit=limit, offset=offset
    )
