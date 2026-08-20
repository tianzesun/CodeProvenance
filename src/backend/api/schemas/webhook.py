"""
Pydantic schemas for webhook-related API requests and responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WebhookEventBase(BaseModel):
    job_id: uuid.UUID
    event_type: str = Field(
        ..., pattern=r"^(job\.completed|job\.failed|job\.progress)$"
    )
    payload: dict[str, Any]
    status: str | None = Field(None, pattern=r"^(pending|delivered|failed|retried)$")
    signature: str | None = None


class WebhookEventCreate(WebhookEventBase):
    pass


class WebhookEventResponse(WebhookEventBase):
    id: uuid.UUID
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None
    delivered_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class WebhookDeliveryConfig(BaseModel):
    secret_key: str = Field(..., min_length=16)
    max_retries: int = Field(3, ge=1, le=10)
    retry_delay_base: int = Field(60, ge=1, le=300)  # seconds
    timeout: int = Field(30, ge=5, le=300)  # seconds
