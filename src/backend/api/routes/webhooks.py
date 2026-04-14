"""
Webhook management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import WebhookEvent
from src.backend.utils.database import WebhookEventService
from src.backend.api.schemas import webhook as webhook_schema

router = APIRouter()

@router.get("/{job_id}", response_model=List[webhook_schema.WebhookEventResponse])
async def get_job_webhook_events(
    job_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Get webhook events for a job.
    """
    # In a real implementation, we would extract tenant_id from API key
    tenant_id = "00000000-0000-0000-0000-000000000001"  # Placeholder
    
    # Set tenant context for RLS
    set_tenant_context(db, str(tenant_id))
    
    # Get webhook events for the job
    events = db.query(WebhookEvent).filter(WebhookEvent.job_id == str(job_id)).all()
    return events
