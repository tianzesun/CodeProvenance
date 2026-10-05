"""
Webhook management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.backend.api.middleware.auth import get_current_tenant
from src.backend.api.schemas import webhook as webhook_schema
from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import WebhookEvent
from src.backend.utils.database import JobService

router = APIRouter()


# Plain ``def``: the session is synchronous, so FastAPI runs this in a worker
# thread instead of blocking the event loop.
@router.get("/{job_id}", response_model=list[webhook_schema.WebhookEventResponse])
def get_job_webhook_events(
    request: Request,
    job_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get webhook events for a job (newest first).
    """
    tenant_id = get_current_tenant(request)

    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))

    # Check ownership explicitly instead of relying on row-level security alone:
    # if RLS is not enabled on webhook_events, filtering by job_id only would
    # expose another tenant's events to anyone who knows a job id.
    if not JobService.get_job_by_id(db, str(job_id), tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    order_column = getattr(WebhookEvent, "created_at", WebhookEvent.id)
    return (
        db.query(WebhookEvent)
        .filter(WebhookEvent.job_id == str(job_id))
        .order_by(order_column.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
