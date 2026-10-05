"""
Pydantic schemas for usage-related API requests and responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: YYYY-MM with a real month. ``\d{2}`` accepted "2026-00" and "2026-99".
PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class UsageBase(BaseModel):
    jobs_processed: int = Field(0, ge=0)
    jobs_successful: int = Field(0, ge=0)
    jobs_failed: int = Field(0, ge=0)
    files_parsed: int = Field(0, ge=0)
    total_size_mb: float = Field(0.0, ge=0.0)
    compute_seconds: float = Field(0.0, ge=0.0)
    api_calls: int = Field(0, ge=0)
    webhook_attempts: int = Field(0, ge=0)
    webhook_deliveries: int = Field(0, ge=0)
    peak_concurrent_jobs: int = Field(0, ge=0)
    storage_used_mb: float = Field(0.0, ge=0.0)


class UsageCreate(UsageBase):
    tenant_id: uuid.UUID
    # ``regex=`` was removed in Pydantic v2 and raises PydanticUserError when the
    # class is defined, so importing this module failed outright.
    period: str = Field(..., pattern=PERIOD_PATTERN)  # YYYY-MM format


class UsageResponse(UsageBase):
    # Also needed for UsageSummary(usage=<ORM row>): a nested model only accepts
    # an arbitrary object when its own config enables from_attributes.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    period: str
    created_at: datetime
    updated_at: datetime | None = None


class UsageSummary(BaseModel):
    tenant_id: uuid.UUID
    current_period: str
    usage: UsageResponse
    # Metric name -> number (the tier table and remaining quota are numeric).
    limits: dict[str, int | float]
    remaining: dict[str, int | float]
