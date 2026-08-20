"""
Pydantic schemas for submission-related API requests and responses.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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
