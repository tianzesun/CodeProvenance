"""Database models for IntegrityDesk.

Design principles (2026-05):
- Strict tenant/organization scoping on all business tables for future multi-tenancy.
- Prefer real ForeignKeys + composite uniqueness over loose ID strings.
- Typed columns for queryable fields; JSONB only for flexible evidence.
- Common mixins for DRY (UUID PK, tenant scoping, timestamps, soft delete).
- Explicit review workflow tables (Case + CaseResult + CaseComment + CaseEvent).
- All timestamps use timezone-aware DateTime.
- Enums for status fields to prevent drift.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime, 
    ForeignKey, JSON, UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.backend.config.database import Base


# =============================================================================
# Shared Mixins (recommended foundation for consistent design)
# =============================================================================

class UUIDPrimaryKeyMixin:
    """Provides a UUID primary key using String(36) for portability."""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class TenantScopedMixin:
    """Adds tenant_id for row-level tenant isolation (supports RLS later)."""
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)


class TimestampMixin:
    """Timezone-aware created/updated timestamps."""
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class SoftDeleteMixin:
    """Optional soft-delete support for user-facing entities (courses, assignments, cases)."""
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Root organization / tenant container.

    This is the top-level scoping entity. It does not use TenantScopedMixin
    (it is the thing being scoped).
    """
    __tablename__ = "tenants"
    
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), unique=True, nullable=False)
    tier = Column(String(50), default="free")
    settings = Column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    
    jobs = relationship("Job", back_populates="tenant", lazy="dynamic")
    api_keys = relationship("ApiKey", back_populates="tenant", lazy="dynamic")
    users = relationship("User", back_populates="tenant", lazy="dynamic")
    courses = relationship("Course", back_populates="tenant", lazy="dynamic")
    assignments = relationship("Assignment", back_populates="tenant", lazy="dynamic")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Dashboard user account.

    tenant_id is nullable to support the initial bootstrap admin before any tenant exists.
    """
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
    )
 
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)
    email = Column(String(255), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="professor")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
 
    tenant = relationship("Tenant", back_populates="users")


class ApiKey(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """API key management model."""
    __tablename__ = "api_keys"
    
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    tenant = relationship("Tenant", back_populates="api_keys")


class Job(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Analysis job model."""
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_tenant_status", "tenant_id", "status"),
    )
    
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=True)
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)
    threshold = Column(Float, default=0.5)
    webhook_url = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    tenant = relationship("Tenant", back_populates="jobs")
    assignment = relationship("Assignment", back_populates="jobs")
    submissions = relationship("Submission", back_populates="job", lazy="dynamic")
    similarity_results = relationship("SimilarityResult", back_populates="job", lazy="dynamic")


class Submission(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Code submission model.

    tenant_id is denormalized here (in addition to job.tenant_id) to enable
    efficient RLS policies and simple filtering without always joining to jobs.
    """
    __tablename__ = "submissions"
    
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    file_count = Column(Integer, default=1)
    language_detected = Column(String(50), nullable=True)

    job = relationship("Job", back_populates="submissions")


class SimilarityResult(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """One suspicious pair result produced by an analysis job.

    tenant_id is denormalized for efficient tenant filtering / RLS.
    """
    __tablename__ = "similarity_results"
    __table_args__ = (
        Index("idx_results_job_score", "job_id", "similarity_score"),
        # UniqueConstraint ensures a given (submission_a, submission_b) pair
        # can only appear once per job. Application code MUST enforce
        # canonical ordering (e.g. always insert with submission_a_id < submission_b_id)
        # so that (a, b) and (b, a) are treated as the same pair and cannot both exist.
        UniqueConstraint(
            "job_id", "submission_a_id", "submission_b_id",
            name="uq_similarity_result_pair_per_job"
        ),
    )
    
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    submission_a_id = Column(String(36), ForeignKey("submissions.id"), nullable=False)
    submission_b_id = Column(String(36), ForeignKey("submissions.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    confidence_lower = Column(Float, nullable=True)
    confidence_upper = Column(Float, nullable=True)

    # Typed columns for filtering/sorting (recommended over JSON for query-heavy fields)
    review_status = Column(String(20), default="pending")      # pending | confirmed | dismissed
    is_above_threshold = Column(Boolean, default=False)
    severity_band = Column(String(10), nullable=True)          # low | medium | high
    pair_rank = Column(Integer, nullable=True)
    cluster_id = Column(String(36), nullable=True)
    engine_name = Column(String(50), nullable=True)

    # Flexible evidence kept in JSONB only
    detected_clones = Column(JSONB, nullable=True)
    matching_blocks = Column(JSONB, nullable=True)
    algorithm_scores = Column(JSONB, nullable=True)
    
    job = relationship("Job", back_populates="similarity_results")
    submission_a = relationship("Submission", foreign_keys=[submission_a_id])
    submission_b = relationship("Submission", foreign_keys=[submission_b_id])


class WebhookEvent(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Webhook event tracking model."""
    __tablename__ = "webhook_events"
    
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")
    payload = Column(JSONB, nullable=True)
    signature = Column(String(255), nullable=True)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    last_error = Column(Text, nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)


class UsageMetric(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Usage tracking model for metering."""
    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_usage_metrics_tenant_period"),
    )
    
    period = Column(String(7), nullable=False)
    jobs_processed = Column(Integer, default=0)
    jobs_successful = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    files_parsed = Column(Integer, default=0)
    total_size_mb = Column(Float, default=0)
    compute_seconds = Column(Float, default=0)
    api_calls = Column(Integer, default=0)
    webhook_attempts = Column(Integer, default=0)
    webhook_deliveries = Column(Integer, default=0)


class AuditLog(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Append-only audit/compliance log.

    tenant_id is required for strong isolation. user_id is now a real FK.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_tenant_action", "tenant_id", "action"),
    )
    
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(36), nullable=True)
    changes = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)


class Course(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Academic course within a tenant workspace.

    Top-level organization-owned entity (eligible for organization_id in future migration).
    """
    __tablename__ = "courses"
    __table_args__ = (
        Index("idx_courses_tenant_name", "tenant_id", "name"),
        Index("idx_courses_tenant_code", "tenant_id", "code"),
    )

    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    tenant = relationship("Tenant", back_populates="courses")
    assignments = relationship("Assignment", back_populates="course", lazy="dynamic")


class Assignment(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Assignment within a course. Groups analysis jobs and cases."""
    __tablename__ = "assignments"
    __table_args__ = (
        Index("idx_assignments_tenant_course", "tenant_id", "course_id"),
        Index("idx_assignments_tenant_name", "tenant_id", "name"),
    )

    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    assignment_mode = Column(String(50), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    threshold = Column(Float, default=0.5)
    description = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    tenant = relationship("Tenant", back_populates="assignments")
    course = relationship("Course", back_populates="assignments")
    jobs = relationship("Job", back_populates="assignment", lazy="dynamic")


class Case(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Faculty review container for suspicious similarity findings.

    A Case is the primary unit of human review workflow. It links to one or more
    SimilarityResult rows via the CaseResult join table.
    """
    __tablename__ = "cases"
    __table_args__ = (
        Index("idx_cases_tenant_assignment", "tenant_id", "assignment_id"),
        Index("idx_cases_status", "status"),
    )

    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    title = Column(String(255), nullable=True)
    status = Column(String(20), default="open")  # open, under_review, resolved, archived
    priority = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    tenant = relationship("Tenant")
    assignment = relationship("Assignment")
    job = relationship("Job")
    results = relationship("CaseResult", back_populates="case", lazy="dynamic")
    comments = relationship("CaseComment", back_populates="case", lazy="dynamic")
    events = relationship("CaseEvent", back_populates="case", lazy="dynamic")


# =============================================================================
# Review Workflow Tables (explicit modeling as recommended)
# =============================================================================

class CaseResult(Base):
    """Join table linking a review Case to one or more suspicious SimilarityResults."""
    __tablename__ = "case_results"
    __table_args__ = (
        UniqueConstraint("case_id", "similarity_result_id", name="uq_case_result"),
        Index("idx_case_results_case", "case_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    similarity_result_id = Column(String(36), ForeignKey("similarity_results.id"), nullable=False)
    review_status = Column(String(20), default="pending")  # pending, confirmed, dismissed
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("Case", back_populates="results")
    similarity_result = relationship("SimilarityResult")


class CaseComment(Base):
    """Faculty notes and discussion history attached to a review Case."""
    __tablename__ = "case_comments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("Case", back_populates="comments")


class CaseEvent(Base):
    """Append-only audit trail of workflow state transitions for a Case."""
    __tablename__ = "case_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("Case", back_populates="events")
