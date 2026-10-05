"""
Pydantic schemas for job-related API requests and responses.
"""

import ipaddress
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.backend.api.schemas.submission import (  # noqa: F401  (re-exported)
    SubmissionBase,
    SubmissionCreate,
    SubmissionResponse,
)
from src.backend.config.settings import settings

__all__ = [
    "JobBase",
    "JobCreate",
    "JobUpdate",
    "JobResponse",
    "SubmissionBase",
    "SubmissionCreate",
    "SubmissionResponse",
]

MAX_RETENTION_DAYS = 365
MAX_LIST_ITEMS = 100
MAX_ITEM_CHARS = 255
MAX_TEMPLATE_FILES = 1000
MAX_WEBHOOK_URL_CHARS = 2048
DEFAULT_EXCLUDE_PATTERNS = ("__pycache__", "*.class", "node_modules")
_BLOCKED_WEBHOOK_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}


def validate_webhook_url(url: str | None) -> str | None:
    """Accept only a public https URL (the server calls it later: SSRF guard).

    The code that *sends* the webhook must still re-check what the host resolves
    to; this rejects the obvious cases at the door.
    """
    if url in (None, ""):
        return None
    text = url.strip()
    if len(text) > MAX_WEBHOOK_URL_CHARS:
        raise ValueError("webhook_url is too long")
    parts = urlsplit(text)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise ValueError("webhook_url must be an https URL without credentials")
    if host in _BLOCKED_WEBHOOK_HOSTS or host.endswith((".local", ".internal")):
        raise ValueError("webhook_url must point to a public host")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return text  # a hostname, not an IP literal
    if not ip.is_global:
        raise ValueError("webhook_url must point to a public host")
    return text


class JobBase(BaseModel):
    """Job fields as stored and returned.

    Only the limits that were already enforced live here. The new request-side
    limits are on :class:`_JobRequestRules`, because this class is also the base
    of JobResponse and a stricter rule would make GET fail for older rows.
    """

    name: str = Field(..., min_length=1, max_length=255)
    assignment_id: str | None = Field(
        None,
        max_length=64,
        description="Link to normalized Assignment (Course/Assignment structure)",
    )
    threshold: float = Field(0.7, ge=0.0, le=1.0)
    webhook_url: str | None = None
    idempotency_key: str | None = Field(None, min_length=1, max_length=255)
    detection_modes: list[str] = Field(
        default_factory=lambda: list(settings.DEFAULT_DETECTION_MODES)
    )
    language_filters: list[str] | None = None
    exclude_patterns: list[str] = Field(
        default_factory=lambda: list(DEFAULT_EXCLUDE_PATTERNS)
    )
    template_files: list[dict[str, Any]] = Field(default_factory=list)
    # The old ``max_days=365`` is not a Pydantic constraint (it was silently
    # ignored), so retention was never capped. The cap is enforced on requests.
    retention_days: int = Field(90, ge=1)

    @field_validator("assignment_id", mode="before")
    @classmethod
    def _assignment_id_as_str(cls, value: Any) -> Any:
        """Accept a UUID object from the ORM (a ``str`` field rejects it in v2)."""
        return str(value) if isinstance(value, uuid.UUID) else value


class _JobRequestRules(BaseModel):
    """Rules for data a client sends (create/update); not applied to responses."""

    @field_validator("webhook_url", check_fields=False)
    @classmethod
    def _webhook_is_safe(cls, value: str | None) -> str | None:
        return validate_webhook_url(value)

    @field_validator("retention_days", check_fields=False)
    @classmethod
    def _retention_cap(cls, value: int | None) -> int | None:
        if value is not None and value > MAX_RETENTION_DAYS:
            raise ValueError(f"retention_days must be at most {MAX_RETENTION_DAYS}")
        return value

    @field_validator(
        "detection_modes", "language_filters", "exclude_patterns", check_fields=False
    )
    @classmethod
    def _bounded_string_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > MAX_LIST_ITEMS or any(len(v) > MAX_ITEM_CHARS for v in value):
            raise ValueError(
                f"at most {MAX_LIST_ITEMS} items of up to {MAX_ITEM_CHARS} characters"
            )
        return value

    @field_validator("template_files", check_fields=False)
    @classmethod
    def _bounded_template_files(
        cls, value: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        if value is not None and len(value) > MAX_TEMPLATE_FILES:
            raise ValueError(f"at most {MAX_TEMPLATE_FILES} template files")
        return value


class JobCreate(_JobRequestRules, JobBase):
    pass


class JobUpdate(_JobRequestRules):
    name: str | None = Field(None, min_length=1, max_length=255)
    threshold: float | None = Field(None, ge=0.0, le=1.0)
    webhook_url: str | None = None
    detection_modes: list[str] | None = None
    language_filters: list[str] | None = None
    exclude_patterns: list[str] | None = None
    template_files: list[dict[str, Any]] | None = None
    retention_days: int | None = Field(None, ge=1)


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

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
