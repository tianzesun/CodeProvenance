"""
Similarity results endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import SimilarityResult
from src.backend.utils.database import SimilarityResultService
from src.backend.api.schemas import result as result_schema

router = APIRouter()

@router.get("/{job_id}", response_model=List[result_schema.ResultResponse])
async def get_job_results(
    job_id: uuid.UUID,
    threshold: Optional[float] = None,
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get similarity results for a job.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Get results
    results = SimilarityResultService.get_results_by_job(
        db=db,
        job_id=str(job_id),
        threshold=threshold,
        limit=limit,
        offset=offset
    )
    return results
