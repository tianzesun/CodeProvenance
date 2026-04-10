"""
Pydantic schemas for job-related API requests and responses.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from src.config.settings import DEFAULT_DETECTION_MODES


class JobBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    threshold: float = Field(0.7, ge=0.0, le=1.0)
    webhook_url: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=255)
    detection_modes: List[str] = Field(default_factory=lambda: list(DEFAULT_DETECTION_MODES))
    language_filters: Optional[List[str]] = None
    exclude_patterns: List[str] = Field(["__pycache__", "*.class", "node_modules"])
    template_files: List[Dict[str, Any]] = Field(default_factory=list)
    retention_days: int = Field(90, ge=1, max_days=365)


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    webhook_url: Optional[str] = None
    detection_modes: Optional[List[str]] = None
    language_filters: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    template_files: Optional[List[Dict[str, Any]]] = None
    retention_days: Optional[int] = Field(None, ge=1, max_days=365)


class JobResponse(JobBase):
    id: uuid.UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    total_submissions: int = 0
    total_pairs_analyzed: int = 0
    high_similarity_count: int = 0
    settings: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


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
