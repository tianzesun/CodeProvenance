"""
Pydantic schemas for usage-related API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


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
    period: str = Field(..., regex=r'^\d{4}-\d{2}$')  # YYYY-MM format


class UsageResponse(UsageBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    period: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class UsageSummary(BaseModel):
    tenant_id: uuid.UUID
    current_period: str
    usage: UsageResponse
    limits: Dict[str, Any]
    remaining: Dict[str, Any]
