"""
Pydantic schemas for job-related API requests and responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.backend.config.settings import settings


class JobBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    assignment_id: str | None = Field(
        None, description="Link to normalized Assignment (Course/Assignment structure)"
    )
    threshold: float = Field(0.7, ge=0.0, le=1.0)
    webhook_url: str | None = None
    idempotency_key: str | None = Field(None, max_length=255)
    detection_modes: list[str] = Field(
        default_factory=lambda: list(settings.DEFAULT_DETECTION_MODES)
    )
    language_filters: list[str] | None = None
    exclude_patterns: list[str] = Field(["__pycache__", "*.class", "node_modules"])
    template_files: list[dict[str, Any]] = Field(default_factory=list)
    retention_days: int = Field(90, ge=1, max_days=365)


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    threshold: float | None = Field(None, ge=0.0, le=1.0)
    webhook_url: str | None = None
    detection_modes: list[str] | None = None
    language_filters: list[str] | None = None
    exclude_patterns: list[str] | None = None
    template_files: list[dict[str, Any]] | None = None
    retention_days: int | None = Field(None, ge=1, max_days=365)


class JobResponse(JobBase):
    id: uuid.UUID
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error_message: str | None = None
    execution_time_ms: int | None = None
    total_submissions: int = 0
    total_pairs_analyzed: int = 0
    high_similarity_count: int = 0
    settings: dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


class SubmissionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    external_id: str | None = Field(None, max_length=255)
    file_paths: list[str] = Field(..., min_items=1)


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionResponse(SubmissionBase):
    id: uuid.UUID
    job_id: uuid.UUID
    file_count: int = 0
    total_size_bytes: int = 0
    language_detected: str | None = None
    languages_detected: list[str] | None = None
    storage_path: str | None = None
    checksum: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    processing_error: str | None = None

    class Config:
        orm_mode = True
