"""
Pydantic schemas for submission-related API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid


class SubmissionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    external_id: Optional[str] = Field(None, max_length=255)
    file_paths: List[str] = Field(..., min_items=1)


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionResponse(SubmissionBase):
    id: uuid.UUID
    job_id: uuid.UUID
    file_count: int = 0
    total_size_bytes: int = 0
    language_detected: Optional[str] = None
    languages_detected: Optional[List[str]] = None
    storage_path: Optional[str] = None
    checksum: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    processing_error: Optional[str] = None

    class Config:
        orm_mode = True
