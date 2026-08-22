"""Database models for IntegrityDesk multi-tenant system."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import relationship

from src.backend.config.database import Base


class Tenant(Base):
    """Multi-tenant isolation model."""

    __tablename__ = "tenants"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
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
    retention_days = Column(Integer, nullable=True, default=365)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    jobs = relationship("Job", back_populates="tenant", lazy="dynamic")
    api_keys = relationship("ApiKey", back_populates="tenant", lazy="dynamic")
    users = relationship("User", back_populates="tenant", lazy="dynamic")

    # New relationships for production tables
    reports = relationship("Report", back_populates="tenant")
    notifications = relationship("Notification", back_populates="tenant")
    subscription = relationship(
        "TenantSubscription", back_populates="tenant", uselist=False
    )


class User(Base):
    """Dashboard user account."""

    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
        Index("idx_users_organization", "organization_id"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=True)
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True
    )
    email = Column(String(255), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="professor")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    tenant = relationship("Tenant", back_populates="users")
    organization = relationship("Organization", back_populates="users")
    courses = relationship("CourseInstructor", back_populates="user", lazy="dynamic")
    # New relationships
    notifications = relationship("Notification", back_populates="user")
    behavioral_sessions = relationship("BehavioralSession", back_populates="user")


class ApiKey(Base):
    """API key management model."""

    __tablename__ = "api_keys"

    __table_args__ = (Index("idx_api_keys_tenant", "tenant_id"),)

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    prefix = Column(String(12), nullable=True)
    permissions = Column(JSONB, default=list)
    rate_limit_override = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="api_keys")


class Job(Base):
    """Analysis job model."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_tenant_status", "tenant_id", "status"),
        Index("idx_jobs_assignment", "assignment_id"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_tenant_created_at", "tenant_id", "created_at"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_status_created_at", "status", "created_at"),
        Index("idx_jobs_tenant_status_created_at", "tenant_id", "status", "created_at"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    assignment_id = Column(
        UUID(as_uuid=False), ForeignKey("assignments.id"), nullable=True
    )
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
    retention_days = Column(Integer, nullable=False, default=90)
    high_similarity_count = Column(Integer, default=0)
    total_pairs_analyzed = Column(Integer, default=0)
    total_submissions = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    failed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    persistence_warning = Column(Text, nullable=True)

    tenant = relationship("Tenant", back_populates="jobs")
    assignment = relationship("Assignment", back_populates="jobs")
    submissions = relationship("Submission", back_populates="job", lazy="dynamic")
    similarity_results = relationship(
        "SimilarityResult", back_populates="job", lazy="dynamic"
    )
    ai_detection_results = relationship(
        "AIDetectionResult", back_populates="job", lazy="dynamic"
    )
    viva_outcomes = relationship("VivaOutcome", back_populates="job", lazy="dynamic")
    # New relationships
    reports = relationship("Report", back_populates="job")
    behavioral_sessions = relationship("BehavioralSession", back_populates="job")


class Submission(Base):
    """Code submission model."""

    __tablename__ = "submissions"

    __table_args__ = (
        Index("idx_submissions_job", "job_id"),
        Index("idx_submissions_created_at", "created_at"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
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
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    job = relationship("Job", back_populates="submissions")
    # New relationship
    behavioral_sessions = relationship("BehavioralSession", back_populates="submission")


class SimilarityResult(Base):
    """Similarity analysis result model."""

    __tablename__ = "similarity_results"
    __table_args__ = (
        Index("idx_results_job_score", "job_id", "similarity_score"),
        Index("idx_similarity_results_review_status", "review_status"),
        Index("idx_similarity_results_verdict", "verdict"),
        Index("idx_similarity_results_created_at", "created_at"),
        Index("idx_similarity_results_submission_a", "submission_a_id"),
        Index("idx_similarity_results_submission_b", "submission_b_id"),
        Index("idx_similarity_results_job_review", "job_id", "review_status"),
        Index(
            "idx_similarity_results_review_created_at", "review_status", "created_at"
        ),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    submission_a_id = Column(String(255), nullable=False)
    submission_b_id = Column(String(255), nullable=False)
    similarity_score = Column(Numeric(5, 4), nullable=False)
    confidence_level = Column(Numeric(3, 2), nullable=True)
    confidence_lower = Column(Numeric(5, 4), nullable=True)
    confidence_upper = Column(Numeric(5, 4), nullable=True)
    matching_blocks = Column(JSONB, nullable=True)
    excluded_matches = Column(JSONB, nullable=True)
    algorithm_scores = Column(JSONB, nullable=True)
    verdict = Column(String(20), nullable=True)  # TRUE, PROBABLE, REVIEW, FLAG, CLEAN
    review_status = Column(String(50), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    job = relationship("Job", back_populates="similarity_results")


class AIDetectionResult(Base):
    """AI-generated code detection result model."""

    __tablename__ = "ai_detection_results"

    __table_args__ = (
        Index("idx_ai_detection_results_job", "job_id"),
        Index("idx_ai_detection_results_job_probability", "job_id", "ai_probability"),
        Index("idx_ai_detection_results_ai_probability", "ai_probability"),
        Index("idx_ai_detection_results_language", "language"),
        Index("idx_ai_detection_results_created_at", "created_at"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    submission_name = Column(String(500), nullable=False)
    language = Column(String(50), nullable=True)
    ai_probability = Column(Numeric(5, 4), nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)
    method = Column(String(50), nullable=True)
    model_name = Column(String(500), nullable=True)
    status = Column(String(50), nullable=True)
    indicators = Column(JSONB, nullable=True)
    signals = Column(JSONB, nullable=True)
    signal_labels = Column(JSONB, nullable=True)
    flagged_lines = Column(JSONB, nullable=True)
    flagged_regions = Column(JSONB, nullable=True)
    classifier_details = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    job = relationship("Job", back_populates="ai_detection_results")


class VivaOutcome(Base):
    """Recorded outcome of a viva (authorship interview) for one submission.

    Closes the dossier's case loop: the instructor interviews the student
    using the generated questions, then records the conclusion here. One row
    per (job, submission); re-recording upserts.
    """

    __tablename__ = "viva_outcomes"

    __table_args__ = (
        Index("idx_viva_outcomes_outcome", "outcome"),
        Index(
            "uq_viva_outcomes_job_submission",
            "job_id",
            "submission_name",
            unique=True,
        ),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    submission_name = Column(String(500), nullable=False)
    # authorship_confirmed | concerns_unresolved | breach_identified | inconclusive
    outcome = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    conducted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    job = relationship("Job", back_populates="viva_outcomes")


class WebhookEvent(Base):
    """Webhook event tracking model."""

    __tablename__ = "webhook_events"

    __table_args__ = (
        Index("idx_webhook_events_job", "job_id"),
        Index("idx_webhook_events_status", "status"),
        Index("idx_webhook_events_next_attempt", "next_attempt_at"),
        Index("idx_webhook_events_status_next_attempt", "status", "next_attempt_at"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    payload = Column(JSONB, nullable=True)
    signature = Column(String(255), nullable=True)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    last_error = Column(Text, nullable=True)
    next_attempt_at = Column(TIMESTAMP(timezone=True), nullable=True)
    delivered_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class UsageMetric(Base):
    """Usage tracking model for metering."""

    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_usage_metrics_tenant_period"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
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
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class AuditLog(Base):
    """Audit log model for compliance."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_tenant_action", "tenant_id", "action"),
        Index("idx_audit_logs_job", "job_id"),
        Index("idx_audit_logs_user", "user_id"),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_tenant_created_at", "tenant_id", "created_at"),
        Index("idx_audit_logs_action", "action"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    user_id = Column(UUID(as_uuid=False), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(UUID(as_uuid=False), nullable=True)
    changes = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


class Organization(Base):
    """Top-level organization / institution (new primary entity)."""

    __tablename__ = "organizations"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    name = Column(String(255), nullable=False)
    settings = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    courses = relationship("Course", back_populates="organization", lazy="dynamic")
    users = relationship("User", back_populates="organization", lazy="dynamic")
    # New relationship
    reports = relationship("Report", back_populates="organization")


class Course(Base):
    """Course within an organization."""

    __tablename__ = "courses"

    __table_args__ = (Index("idx_courses_organization", "organization_id"),)

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False
    )
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    settings = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    organization = relationship("Organization", back_populates="courses")
    assignments = relationship("Assignment", back_populates="course", lazy="dynamic")
    instructors = relationship(
        "CourseInstructor", back_populates="course", lazy="dynamic"
    )


class Assignment(Base):
    """Assignment within a course."""

    __tablename__ = "assignments"

    __table_args__ = (Index("idx_assignments_course", "course_id"),)

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    course_id = Column(UUID(as_uuid=False), ForeignKey("courses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    due_at = Column(TIMESTAMP(timezone=True), nullable=True)
    settings = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    course = relationship("Course", back_populates="assignments")
    jobs = relationship("Job", back_populates="assignment", lazy="dynamic")


class CourseInstructor(Base):
    """Many-to-many association between courses and instructors (professors)."""

    __tablename__ = "course_instructors"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    course_id = Column(
        UUID(as_uuid=False),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(
        String(50), default="instructor"
    )  # instructor, primary, ta, assistant
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

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

    __table_args__ = (
        Index("idx_cases_organization", "organization_id"),
        Index("idx_cases_assignment", "assignment_id"),
        Index("idx_cases_created_by", "created_by_id"),
        Index("idx_cases_status", "status"),
        Index("idx_cases_created_at", "created_at"),
        Index("idx_cases_org_created_at", "organization_id", "created_at"),
        Index("idx_cases_org_status", "organization_id", "status"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False
    )
    assignment_id = Column(
        UUID(as_uuid=False), ForeignKey("assignments.id"), nullable=True
    )
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="OPEN")  # OPEN, UNDER_REVIEW, ESCALATED, CLOSED
    priority = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, URGENT
    investigator_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_by_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )
    closed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    organization = relationship("Organization")
    assignment = relationship("Assignment")
    investigator = relationship("User", foreign_keys=[investigator_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    result_links = relationship("CaseResultLink", back_populates="case", lazy="dynamic")
    comments = relationship("CaseComment", back_populates="case", lazy="dynamic")
    reports = relationship("Report", back_populates="case")


class CaseResultLink(Base):
    """Link between a Case and a SimilarityResult."""

    __tablename__ = "case_result_links"

    __table_args__ = (
        Index("idx_case_result_links_case", "case_id"),
        Index("idx_case_result_links_similarity_result", "similarity_result_id"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id"), nullable=False)
    similarity_result_id = Column(
        UUID(as_uuid=False), ForeignKey("similarity_results.id"), nullable=False
    )
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    case = relationship("Case", back_populates="result_links")
    similarity_result = relationship("SimilarityResult")


class CaseComment(Base):
    """Comment on a review Case."""

    __tablename__ = "case_comments"

    __table_args__ = (
        Index("idx_case_comments_case", "case_id"),
        Index("idx_case_comments_user", "user_id"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    case = relationship("Case", back_populates="comments")
    user = relationship("User")


# ============================================================
# NEW MODELS - Added for production readiness
# ============================================================


class Report(Base):
    """Generated professional reports (PDF, HTML, JSON, etc.)."""

    __tablename__ = "reports"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True
    )

    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True
    )
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id"), nullable=True)

    report_type = Column(String(50), nullable=False)
    format = Column(String(20), nullable=False)
    version = Column(String(20), nullable=False, default="1.0")

    status = Column(String(20), nullable=False, default="generating")
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)

    generated_by_user_id = Column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    generated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # ← Fixed: renamed from 'metadata' to 'report_metadata'
    report_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    __table_args__ = (
        Index("idx_reports_tenant_status", "tenant_id", "status"),
        Index("idx_reports_job", "job_id"),
        Index("idx_reports_case", "case_id"),
        Index("idx_reports_generated_at", "generated_at"),
        Index("idx_reports_tenant_type", "tenant_id", "report_type"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="reports")
    organization = relationship("Organization", back_populates="reports")
    job = relationship("Job", back_populates="reports")
    case = relationship("Case", back_populates="reports")
    generated_by = relationship("User", foreign_keys=[generated_by_user_id])


class Notification(Base):
    """User notifications (in-app, email, Slack, etc.)."""

    __tablename__ = "notifications"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)

    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    related_job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True
    )
    related_case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id"), nullable=True)
    related_report_id = Column(
        UUID(as_uuid=False), ForeignKey("reports.id"), nullable=True
    )

    channel = Column(String(20), nullable=False, default="in_app")
    priority = Column(String(20), nullable=False, default="normal")

    status = Column(String(20), nullable=False, default="pending")
    read_at = Column(TIMESTAMP(timezone=True), nullable=True)
    sent_at = Column(TIMESTAMP(timezone=True), nullable=True)

    payload = Column(JSONB, nullable=False, default=dict)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("idx_notifications_user_status", "user_id", "status"),
        Index("idx_notifications_tenant_created", "tenant_id", "created_at"),
        Index("idx_notifications_type", "type"),
    )

    # Relationships
    user = relationship("User", back_populates="notifications")
    tenant = relationship("Tenant", back_populates="notifications")
    job = relationship("Job")
    case = relationship("Case")
    report = relationship("Report")


class BehavioralSession(Base):
    """Behavioral / keystroke data for plagiarism detection."""

    __tablename__ = "behavioral_sessions"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    submission_id = Column(
        UUID(as_uuid=False), ForeignKey("submissions.id"), nullable=False
    )
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    session_id = Column(String(100), nullable=True)
    keystroke_count = Column(Integer, default=0)
    paste_count = Column(Integer, default=0)
    focus_loss_count = Column(Integer, default=0)
    typing_speed_wpm = Column(Float, nullable=True)

    risk_score = Column(Numeric(4, 3), nullable=True)
    patterns = Column(JSONB, nullable=False, default=dict)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("idx_behavioral_sessions_submission", "submission_id"),
        Index("idx_behavioral_sessions_job", "job_id"),
        Index("idx_behavioral_sessions_user", "user_id"),
        Index("idx_behavioral_sessions_risk", "risk_score"),
    )

    # Relationships
    submission = relationship("Submission", back_populates="behavioral_sessions")
    job = relationship("Job", back_populates="behavioral_sessions")
    user = relationship("User", back_populates="behavioral_sessions")


class TenantSubscription(Base):
    """Subscription and plan management per tenant."""

    __tablename__ = "tenant_subscriptions"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    tenant_id = Column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, unique=True
    )

    plan = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)

    current_period_start = Column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end = Column(TIMESTAMP(timezone=True), nullable=True)
    trial_end = Column(TIMESTAMP(timezone=True), nullable=True)

    job_limit = Column(Integer, nullable=True)
    storage_limit_mb = Column(Integer, nullable=True)
    features = Column(JSONB, nullable=False, default=dict)

    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    __table_args__ = (Index("idx_tenant_subscriptions_status", "status"),)

    # Relationships
    tenant = relationship("Tenant", back_populates="subscription")


class FprValidationRun(Base):
    """Stored Real FPR Validation runs for audit, comparison, and certification.

    These are professor/admin-initiated tests on known-clean student corpora
    to measure actual false positive risk before using the system in production courses.
    """

    __tablename__ = "fpr_validation_runs"

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    payload = Column(JSONB, nullable=False)  # full result from /api/benchmark/real-fpr

    # Denormalized key metrics for fast filtering/listing without loading full payload
    num_submissions = Column(Integer, nullable=True)
    num_pairs = Column(Integer, nullable=True)
    mean_score = Column(Numeric(5, 4), nullable=True)
    max_score = Column(Numeric(5, 4), nullable=True)

    # Key decision values captured at the time of the run
    recommended_threshold = Column(Numeric(5, 2), nullable=True)
    fpr_at_recommended_threshold = Column(Numeric(6, 4), nullable=True)

    # User-provided notes and workflow status
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="completed")

    # Future-proofing for certification workflow
    is_certified = Column(Boolean, nullable=False, default=False)
    certified_by_user_id = Column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    certified_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("idx_fpr_runs_tenant_created", "tenant_id", "created_at"),
        Index("idx_fpr_runs_user", "user_id"),
        Index("idx_fpr_runs_tenant_status", "tenant_id", "status"),
        Index("idx_fpr_runs_certified", "is_certified"),
    )

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User", foreign_keys=[user_id])
    certified_by = relationship("User", foreign_keys=[certified_by_user_id])


class TimelineEvent(Base):
    """Timeline event for investigation audit trail."""

    __tablename__ = "timeline_events"

    __table_args__ = (
        Index("idx_timeline_case", "case_id"),
        Index("idx_timeline_job", "job_id"),
        Index("idx_timeline_user", "user_id"),
        Index("idx_timeline_created_at", "created_at"),
        Index("idx_timeline_case_created", "case_id", "created_at"),
    )

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id"), nullable=True)
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True
    )
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    event_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=False, default=dict)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    case = relationship("Case")
    job = relationship("Job")
    user = relationship("User")
