"""
Pydantic schemas for webhook-related API requests and responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    # ``orm_mode`` is the Pydantic v1 spelling. The rest of the code base is on
    # v2 (it uses ``from_attributes``, ``model_fields_set``, ``pattern=``), where
    # ``orm_mode`` is ignored with a warning, so these models could not be built
    # from ORM rows.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attempt_count: int = Field(0, ge=0)
    max_attempts: int = Field(..., ge=1)
    # Optional fields had no default, which makes them *required* in v2.
    next_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    # Usually NULL until the first update, so it must not be required.
    updated_at: datetime | None = None


class WebhookDeliveryConfig(BaseModel):
    # The signing secret must not leak through ``repr()`` (log lines, tracebacks,
    # debuggers) or ``model_dump()`` (JSON responses, serialised config).
    # Attribute access still returns the plain string.
    secret_key: str = Field(..., min_length=16, repr=False, exclude=True)
    max_retries: int = Field(3, ge=1, le=10)
    retry_delay_base: int = Field(60, ge=1, le=300)  # seconds
    timeout: int = Field(30, ge=5, le=300)  # seconds
