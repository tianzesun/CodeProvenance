"""
Pydantic schemas for webhook-related API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class WebhookEventBase(BaseModel):
    job_id: uuid.UUID
    event_type: str = Field(..., regex=r'^(job\.completed|job\.failed|job\.progress)$')
    payload: Dict[str, Any]
    status: Optional[str] = Field(None, regex=r'^(pending|delivered|failed|retried)$')
    signature: Optional[str] = None


class WebhookEventCreate(WebhookEventBase):
    pass


class WebhookEventResponse(WebhookEventBase):
    id: uuid.UUID
    attempt_count: int
    max_attempts: int
    next_attempt_at: Optional[datetime]
    delivered_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class WebhookDeliveryConfig(BaseModel):
    secret_key: str = Field(..., min_length=16)
    max_retries: int = Field(3, ge=1, le=10)
    retry_delay_base: int = Field(60, ge=1, le=300)  # seconds
    timeout: int = Field(30, ge=5, le=300)  # seconds