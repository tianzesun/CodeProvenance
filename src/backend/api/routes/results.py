"""
Similarity results endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.schemas import result as result_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.utils.database import SimilarityResultService

router = APIRouter()


@router.get("/{job_id}", response_model=list[result_schema.ResultResponse])
async def get_job_results(
    request: Request,
    job_id: uuid.UUID,
    threshold: float | None = None,
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Get similarity results for a job.
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Get results
    results = SimilarityResultService.get_results_by_job(
        db=db, job_id=str(job_id), threshold=threshold, limit=limit, offset=offset
    )
    return results
