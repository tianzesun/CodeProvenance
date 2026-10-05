"""
Pydantic schemas for submission-related API requests and responses.
"""

import uuid
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_FILE_PATHS = 1000
MAX_PATH_CHARS = 1024

SubmissionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


def validate_relative_paths(paths: list[str]) -> list[str]:
    """Reject absolute paths, ``..`` and NUL in client-supplied file paths.

    They are stored and later opened by the analysis pipeline, so an unchecked
    ``/etc/passwd`` or ``../../secrets`` is an arbitrary file read.
    """
    for raw in paths:
        if not raw or len(raw) > MAX_PATH_CHARS or "\x00" in raw:
            raise ValueError(f"file paths must be 1-{MAX_PATH_CHARS} characters, no NUL")
        normalized = raw.replace("\\", "/")
        if (
            PurePosixPath(normalized).is_absolute()
            or PureWindowsPath(raw).is_absolute()
            or ".." in PurePosixPath(normalized).parts
        ):
            raise ValueError("file paths must be relative and must not contain '..'")
    return paths


class SubmissionBase(BaseModel):
    name: SubmissionName
    external_id: str | None = Field(None, max_length=255)
    # Lenient on purpose: this class is also the base of the *response*. The
    # request-side rules live on SubmissionCreate so a stored row with no files
    # or an older path format cannot turn a GET into a 500.
    file_paths: list[str] = Field(default_factory=list)


class SubmissionCreate(SubmissionBase):
    # ``min_items`` is the Pydantic v1 name (deprecated in v2). The list and each
    # path were also unbounded.
    file_paths: list[str] = Field(..., min_length=1, max_length=MAX_FILE_PATHS)

    @field_validator("file_paths")
    @classmethod
    def _paths_are_relative(cls, paths: list[str]) -> list[str]:
        return validate_relative_paths(paths)


class SubmissionResponse(SubmissionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    file_count: int = Field(0, ge=0)
    total_size_bytes: int = Field(0, ge=0)
    language_detected: str | None = None
    languages_detected: list[str] | None = None
    # The absolute directory on the server: kept for internal use, never serialised.
    storage_path: str | None = Field(None, exclude=True)
    checksum: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    processing_error: str | None = None
