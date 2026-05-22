"""Database models for IntegrityDesk multi-tenant system."""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime, 
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum,
    Numeric, BigInteger, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, TIMESTAMP

from src.backend.config.database import Base


class Tenant(Base):
    """Multi-tenant isolation model."""
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), unique=True, nullable=False)
    tier = Column(String(50), default="free")
    status = Column(String(20), default="active")
    settings = Column(JSONB, default=dict)
    trial_ends_at = Column(TIMESTAMP(timezone=True), nullable=True)
    monthly_job_limit = Column(Integer, nullable=True)
    concurrent_job_limit = Column(Integer, nullable=True)
    max_payload_mb = Column(Integer, nullable=True)
    rate_limit_per_minute = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))
    
    jobs = relationship("Job", back_populates="tenant", lazy="dynamic")
    api_keys = relationship("ApiKey", back_populates="tenant", lazy="dynamic")
    users = relationship("User", back_populates="tenant", lazy="dynamic")


class User(Base):
    """Dashboard user account."""
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=True)
    organization_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True)
    email = Column(String(255), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="professor")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))

    tenant = relationship("Tenant", back_populates="users")
    organization = relationship("Organization", back_populates="users")
    courses = relationship("CourseInstructor", back_populates="user", lazy="dynamic")


class ApiKey(Base):
    """API key management model."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    prefix = Column(String(12), nullable=True)
    permissions = Column(JSONB, default=list)
    rate_limit_override = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    tenant = relationship("Tenant", back_populates="api_keys")


class Job(Base):
    """Analysis job model."""
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_tenant_status", "tenant_id", "status"),
    )
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    assignment_id = Column(UUID(as_uuid=False), ForeignKey("assignments.id"), nullable=True)
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="pending")
    threshold = Column(Numeric(3, 2), default=0.5)
    webhook_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    detection_modes = Column(JSONB, nullable=True)
    exclude_patterns = Column(JSONB, nullable=True)
    language_filters = Column(JSONB, nullable=True)
    template_files = Column(JSONB, nullable=True)
    settings = Column(JSONB, nullable=True)
    idempotency_key = Column(String(255), nullable=True, unique=True)
    retention_days = Column(Integer, nullable=True)
    high_similarity_count = Column(Integer, default=0)
    total_pairs_analyzed = Column(Integer, default=0)
    total_submissions = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    failed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    tenant = relationship("Tenant", back_populates="jobs")
    assignment = relationship("Assignment", back_populates="jobs")
    submissions = relationship("Submission", back_populates="job", lazy="dynamic")
    similarity_results = relationship("SimilarityResult", back_populates="job", lazy="dynamic")


class Submission(Base):
    """Code submission model."""
    __tablename__ = "submissions"
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    file_count = Column(Integer, default=1)
    language_detected = Column(String(50), nullable=True)
    languages_detected = Column(JSONB, nullable=True)
    checksum = Column(String(64), nullable=True)
    external_id = Column(String(255), nullable=True)
    storage_path = Column(String(500), nullable=True)
    file_paths = Column(JSONB, nullable=True)
    total_size_bytes = Column(BigInteger, nullable=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    
    job = relationship("Job", back_populates="submissions")


class SimilarityResult(Base):
    """Similarity analysis result model."""
    __tablename__ = "similarity_results"
    __table_args__ = (
        Index("idx_results_job_score", "job_id", "similarity_score"),
    )
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    submission_a_id = Column(UUID(as_uuid=False), nullable=False)
    submission_b_id = Column(UUID(as_uuid=False), nullable=False)
    similarity_score = Column(Numeric(5, 4), nullable=False)
    confidence_level = Column(Numeric(3, 2), nullable=True)
    confidence_lower = Column(Numeric(5, 4), nullable=True)
    confidence_upper = Column(Numeric(5, 4), nullable=True)
    matching_blocks = Column(JSONB, nullable=True)
    excluded_matches = Column(JSONB, nullable=True)
    algorithm_scores = Column(JSONB, nullable=True)
    review_status = Column(String(50), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))
    
    job = relationship("Job", back_populates="similarity_results")


class WebhookEvent(Base):
    """Webhook event tracking model."""
    __tablename__ = "webhook_events"
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    payload = Column(JSONB, nullable=True)
    signature = Column(String(255), nullable=True)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    last_error = Column(Text, nullable=True)
    next_attempt_at = Column(TIMESTAMP(timezone=True), nullable=True)
    delivered_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))


class UsageMetric(Base):
    """Usage tracking model for metering."""
    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_usage_metrics_tenant_period"),
    )
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    period = Column(String(7), nullable=False)
    jobs_processed = Column(Integer, default=0)
    jobs_successful = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    files_parsed = Column(Integer, default=0)
    total_size_mb = Column(Float, default=0)
    storage_used_mb = Column(Numeric(10, 2), default=0)
    compute_seconds = Column(Numeric(10, 2), default=0)
    api_calls = Column(Integer, default=0)
    webhook_attempts = Column(Integer, default=0)
    webhook_deliveries = Column(Integer, default=0)
    peak_concurrent_jobs = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))


class AuditLog(Base):
    """Audit log model for compliance."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_tenant_action", "tenant_id", "action"),
    )
    
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=True)
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)
    user_id = Column(UUID(as_uuid=False), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(UUID(as_uuid=False), nullable=True)
    changes = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))


class Organization(Base):
    """Top-level organization / institution (new primary entity)."""
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    name = Column(String(255), nullable=False)
    settings = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))

    courses = relationship("Course", back_populates="organization", lazy="dynamic")
    users = relationship("User", back_populates="organization", lazy="dynamic")


class Course(Base):
    """Course within an organization."""
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    organization_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    settings = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))

    organization = relationship("Organization", back_populates="courses")
    assignments = relationship("Assignment", back_populates="course", lazy="dynamic")
    instructors = relationship("CourseInstructor", back_populates="course", lazy="dynamic")


class Assignment(Base):
    """Assignment within a course."""
    __tablename__ = "assignments"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    course_id = Column(UUID(as_uuid=False), ForeignKey("courses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    due_at = Column(TIMESTAMP(timezone=True), nullable=True)
    settings = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))

    course = relationship("Course", back_populates="assignments")
    jobs = relationship("Job", back_populates="assignment", lazy="dynamic")


class CourseInstructor(Base):
    """Many-to-many association between courses and instructors (professors)."""
    __tablename__ = "course_instructors"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    course_id = Column(UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), default="instructor")  # instructor, primary, ta, assistant
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))

    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_instructor"),
        Index("idx_course_instructors_course", "course_id"),
        Index("idx_course_instructors_user", "user_id"),
    )

    course = relationship("Course", back_populates="instructors")
    user = relationship("User", back_populates="courses")


class Case(Base):
    """Instructor review case for grouping similarity results."""
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    organization_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False)
    assignment_id = Column(UUID(as_uuid=False), ForeignKey("assignments.id"), nullable=True)
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="open")
    created_by_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), onupdate=text('now()'))

    organization = relationship("Organization")
    assignment = relationship("Assignment")
    created_by = relationship("User")
    result_links = relationship("CaseResultLink", back_populates="case", lazy="dynamic")
    comments = relationship("CaseComment", back_populates="case", lazy="dynamic")


class CaseResultLink(Base):
    """Link between a Case and a SimilarityResult."""
    __tablename__ = "case_result_links"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id"), nullable=False)
    similarity_result_id = Column(UUID(as_uuid=False), ForeignKey("similarity_results.id"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))

    case = relationship("Case", back_populates="result_links")
    similarity_result = relationship("SimilarityResult")


class CaseComment(Base):
    """Comment on a review Case."""
    __tablename__ = "case_comments"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=text('uuid_generate_v4()'))
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))

    case = relationship("Case", back_populates="comments")
    user = relationship("User")
