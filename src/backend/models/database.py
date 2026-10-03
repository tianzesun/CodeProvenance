"""Database models for IntegrityDesk multi-tenant system.

Conventions used throughout this module
---------------------------------------
* Foreign keys state what happens on delete. Rows *owned by* a job (submissions, results, viva outcomes, webhook
  events) are deleted with it (``CASCADE``); rows that only *refer to* something and must outlive it (audit logs,
  notifications, reports) are detached (``SET NULL``). The matching relationships use ``passive_deletes=True`` so the
  ORM leaves the work to the database instead of nulling the key itself.
* Score and rate columns come back as ``float`` (``asdecimal=False``), not ``Decimal``, so they serialise to JSON
  numbers and mix with ordinary arithmetic.
* JSONB columns that default to ``{}`` or ``[]`` are mutable-tracked, so editing one in place
  (``tenant.settings["x"] = 1``) is saved. Plain ``JSONB`` columns still need reassignment.
* Index and constraint names are explicit and unique across the schema (PostgreSQL requires that for indexes).
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
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
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import relationship

from src.backend.config.database import Base

# ── Shared building blocks ───────────────────────────────────────────────────

#: Submission and file names. These were String(255) on some tables and String(500) on others, so a long name
#: (a path inside a ZIP, say) could be stored in one table and rejected by the next.
SUBMISSION_NAME_LENGTH = 500

JSONDict = MutableDict.as_mutable(JSONB)
JSONList = MutableList.as_mutable(JSONB)

# Closed sets that the code comments already documented; the CHECK constraints below enforce them.
VIVA_OUTCOMES = ("authorship_confirmed", "concerns_unresolved", "breach_identified", "inconclusive")
PAIR_BANDS = ("low", "review", "high")
PAIR_DISPOSITIONS = ("no_action", "note_on_file", "conversation", "step_up_verification", "formal_escalation")
APPEAL_STATUSES = ("submitted", "under_review", "upheld", "overturned")


def _in(column: str, values: tuple[str, ...]) -> str:
    """SQL ``column IN ('a', 'b', ...)`` for a fixed tuple of constants."""
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def uuid_pk() -> Column:
    # gen_random_uuid() is built into PostgreSQL 13+. The previous uuid_generate_v4() needs the uuid-ossp extension,
    # which nothing in the code created, so a fresh database failed on the first insert.
    return Column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))


def created_at_column() -> Column:
    return Column(TIMESTAMP(timezone=True), server_default=text("now()"))


def updated_at_column() -> Column:
    return Column(TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=text("now()"))


def score_type(precision: int, scale: int) -> Numeric:
    return Numeric(precision, scale, asdecimal=False)


class Tenant(Base):
    """Multi-tenant isolation model."""

    __tablename__ = "tenants"

    id = uuid_pk()
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), unique=True, nullable=False)
    tier = Column(String(50), default="free")
    status = Column(String(20), default="active")
    settings = Column(JSONDict, default=dict)
    trial_ends_at = Column(TIMESTAMP(timezone=True), nullable=True)
    monthly_job_limit = Column(Integer, nullable=True)
    concurrent_job_limit = Column(Integer, nullable=True)
    max_payload_mb = Column(Integer, nullable=True)
    rate_limit_per_minute = Column(Integer, nullable=True)
    retention_days = Column(Integer, nullable=True, default=365)
    created_at = created_at_column()
    updated_at = updated_at_column()

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
        Index("idx_users_role", "role"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
        Index("idx_users_organization", "organization_id"),
    )

    id = uuid_pk()
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
    # SECURITY: store a SHA-256 of the token here, never the token itself, and compare hashes. A database leak
    # (backup, replica, SQL injection) should not hand out working password-reset and verification links.
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(TIMESTAMP(timezone=True), nullable=True)
    #: Email-verification token for self-registered accounts. The account
    #: stays ``is_active=False`` until this token is redeemed, so the inbox
    #: is proven before the credential ever works.
    verify_token = Column(String(255), nullable=True)
    verify_token_expires = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = created_at_column()
    updated_at = updated_at_column()

    tenant = relationship("Tenant", back_populates="users")
    organization = relationship("Organization", back_populates="users")
    courses = relationship(
        "CourseInstructor", back_populates="user", lazy="dynamic", passive_deletes=True
    )
    # New relationships
    notifications = relationship("Notification", back_populates="user")
    behavioral_sessions = relationship("BehavioralSession", back_populates="user")


class ApiKey(Base):
    """API key management model."""

    __tablename__ = "api_keys"

    __table_args__ = (Index("idx_api_keys_tenant", "tenant_id"),)

    id = uuid_pk()
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    prefix = Column(String(12), nullable=True)
    permissions = Column(JSONList, default=list)
    rate_limit_override = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = created_at_column()
    updated_at = updated_at_column()
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="api_keys")


class Job(Base):
    """Analysis job model."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_assignment", "assignment_id"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_tenant_created_at", "tenant_id", "created_at"),
        Index("idx_jobs_status_created_at", "status", "created_at"),
        Index("idx_jobs_tenant_status_created_at", "tenant_id", "status", "created_at"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_jobs_tenant_idempotency_key"),
        CheckConstraint("threshold >= 0 AND threshold <= 1", name="ck_jobs_threshold_range"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    assignment_id = Column(
        UUID(as_uuid=False), ForeignKey("assignments.id"), nullable=True
    )
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="pending")
    threshold = Column(score_type(3, 2), default=0.5)
    webhook_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    detection_modes = Column(JSONB, nullable=True)
    exclude_patterns = Column(JSONB, nullable=True)
    language_filters = Column(JSONB, nullable=True)
    template_files = Column(JSONB, nullable=True)
    settings = Column(JSONB, nullable=True)
    # Unique per tenant (see __table_args__). It was unique across *all* tenants, so one tenant's key could
    # collide with, or reveal the existence of, another tenant's job.
    idempotency_key = Column(String(255), nullable=True)
    retention_days = Column(Integer, nullable=False, default=90)
    high_similarity_count = Column(Integer, default=0)
    total_pairs_analyzed = Column(Integer, default=0)
    total_submissions = Column(Integer, default=0)
    created_at = created_at_column()
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    failed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    persistence_warning = Column(Text, nullable=True)

    tenant = relationship("Tenant", back_populates="jobs")
    assignment = relationship("Assignment", back_populates="jobs")
    submissions = relationship(
        "Submission", back_populates="job", lazy="dynamic", passive_deletes=True
    )
    similarity_results = relationship(
        "SimilarityResult", back_populates="job", lazy="dynamic", passive_deletes=True
    )
    ai_detection_results = relationship(
        "AIDetectionResult", back_populates="job", lazy="dynamic", passive_deletes=True
    )
    viva_outcomes = relationship(
        "VivaOutcome", back_populates="job", lazy="dynamic", passive_deletes=True
    )
    # New relationships
    # These two keys are ON DELETE CASCADE. Without passive_deletes the ORM nulled them first: behavioral sessions
    # (NOT NULL job_id) made deleting a job fail, and reports survived as orphans with job_id NULL.
    reports = relationship("Report", back_populates="job", passive_deletes=True)
    behavioral_sessions = relationship(
        "BehavioralSession", back_populates="job", passive_deletes=True
    )


class Submission(Base):
    """Code submission model."""

    __tablename__ = "submissions"

    __table_args__ = (
        Index("idx_submissions_job", "job_id"),
        Index("idx_submissions_student", "student_id"),
        Index("idx_submissions_created_at", "created_at"),
    )

    id = uuid_pk()
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID(as_uuid=False), ForeignKey("students.id"), nullable=True)
    name = Column(String(SUBMISSION_NAME_LENGTH), nullable=False)
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
    created_at = created_at_column()

    job = relationship("Job", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")
    # New relationship
    behavioral_sessions = relationship(
        "BehavioralSession", back_populates="submission", passive_deletes=True
    )


class SimilarityResult(Base):
    """Similarity analysis result model."""

    __tablename__ = "similarity_results"
    __table_args__ = (
        Index("idx_results_job_score", "job_id", "similarity_score"),
        Index("idx_similarity_results_verdict", "verdict"),
        Index("idx_similarity_results_created_at", "created_at"),
        Index("idx_similarity_results_submission_a", "submission_a_id"),
        Index("idx_similarity_results_submission_b", "submission_b_id"),
        Index("idx_similarity_results_job_review", "job_id", "review_status"),
        Index(
            "idx_similarity_results_review_created_at", "review_status", "created_at"
        ),
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="ck_similarity_results_score_range",
        ),
    )

    id = uuid_pk()
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    # Despite the "_id" suffix these hold submission *names*, not submissions.id: there is no foreign key.
    submission_a_id = Column(String(SUBMISSION_NAME_LENGTH), nullable=False)
    submission_b_id = Column(String(SUBMISSION_NAME_LENGTH), nullable=False)
    similarity_score = Column(score_type(5, 4), nullable=False)
    confidence_level = Column(score_type(3, 2), nullable=True)
    confidence_lower = Column(score_type(5, 4), nullable=True)
    confidence_upper = Column(score_type(5, 4), nullable=True)
    matching_blocks = Column(JSONB, nullable=True)
    excluded_matches = Column(JSONB, nullable=True)
    algorithm_scores = Column(JSONB, nullable=True)
    # Legacy labels: TRUE, PROBABLE, REVIEW, FLAG, CLEAN. Newer ones (STRONG_SIMILARITY_OBSERVED, REVIEW_REQUIRED)
    # are up to 26 characters, which did not fit the previous String(20).
    verdict = Column(String(40), nullable=True)
    review_status = Column(String(50), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = created_at_column()
    updated_at = updated_at_column()

    job = relationship("Job", back_populates="similarity_results")


class AIDetectionResult(Base):
    """AI-generated code detection result model."""

    __tablename__ = "ai_detection_results"

    __table_args__ = (
        Index("idx_ai_detection_results_job_probability", "job_id", "ai_probability"),
        Index("idx_ai_detection_results_ai_probability", "ai_probability"),
        Index("idx_ai_detection_results_language", "language"),
        Index("idx_ai_detection_results_created_at", "created_at"),
        CheckConstraint(
            "ai_probability IS NULL OR (ai_probability >= 0 AND ai_probability <= 1)",
            name="ck_ai_detection_results_probability_range",
        ),
    )

    id = uuid_pk()
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    submission_name = Column(String(500), nullable=False)
    language = Column(String(50), nullable=True)
    ai_probability = Column(score_type(5, 4), nullable=True)
    confidence = Column(score_type(3, 2), nullable=True)
    method = Column(String(50), nullable=True)
    model_name = Column(String(500), nullable=True)
    status = Column(String(50), nullable=True)
    indicators = Column(JSONB, nullable=True)
    signals = Column(JSONB, nullable=True)
    signal_labels = Column(JSONB, nullable=True)
    flagged_lines = Column(JSONB, nullable=True)
    flagged_regions = Column(JSONB, nullable=True)
    classifier_details = Column(JSONB, nullable=True)
    created_at = created_at_column()

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
        CheckConstraint(_in("outcome", VIVA_OUTCOMES), name="ck_viva_outcomes_outcome"),
    )

    id = uuid_pk()
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    submission_name = Column(String(500), nullable=False)
    # authorship_confirmed | concerns_unresolved | breach_identified | inconclusive
    outcome = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    conducted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = created_at_column()
    updated_at = updated_at_column()

    job = relationship("Job", back_populates="viva_outcomes")


class WebhookEvent(Base):
    """Webhook event tracking model."""

    __tablename__ = "webhook_events"

    __table_args__ = (
        Index("idx_webhook_events_job", "job_id"),
        Index("idx_webhook_events_next_attempt", "next_attempt_at"),
        Index("idx_webhook_events_status_next_attempt", "status", "next_attempt_at"),
    )

    id = uuid_pk()
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    payload = Column(JSONB, nullable=True)
    signature = Column(String(255), nullable=True)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    last_error = Column(Text, nullable=True)
    next_attempt_at = Column(TIMESTAMP(timezone=True), nullable=True)
    delivered_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = created_at_column()
    updated_at = updated_at_column()


class UsageMetric(Base):
    """Usage tracking model for metering."""

    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_usage_metrics_tenant_period"),
    )

    id = uuid_pk()
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
    created_at = created_at_column()
    updated_at = updated_at_column()


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

    id = uuid_pk()
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=True)
    # SET NULL: the audit trail has to survive the purge of the job it describes. With no ON DELETE, one audit
    # row for a job made that job impossible to delete.
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(UUID(as_uuid=False), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(UUID(as_uuid=False), nullable=True)
    changes = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = created_at_column()


class Organization(Base):
    """Top-level organization / institution (new primary entity)."""

    __tablename__ = "organizations"

    id = uuid_pk()
    name = Column(String(255), nullable=False)
    settings = Column(JSONDict, default=dict)
    created_at = created_at_column()
    updated_at = updated_at_column()

    courses = relationship("Course", back_populates="organization", lazy="dynamic")
    users = relationship("User", back_populates="organization", lazy="dynamic")
    # New relationship
    reports = relationship("Report", back_populates="organization")


class Term(Base):
    """Academic term (e.g. ``Fall 2026``) within an organization.

    A term is a first-class, organization-scoped entity so a new term can be
    created up front and then assigned to one or more courses. The
    ``(organization_id, name, year)`` triple is unique, which lets the same term
    name recur across years ("Fall 2026" vs "Fall 2027") without collision.

    Courses keep their denormalized ``term``/``year`` text columns in sync with
    their ``term_id`` reference. Those columns are read by existing reporting
    and historical-matching queries, so they are retained rather than replaced.
    """

    __tablename__ = "terms"

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", "year", name="uq_terms_org_name_year"
        ),
        Index("idx_terms_org_year", "organization_id", "year"),
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="ck_terms_date_order",
        ),
    )

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False
    )
    # Season name, e.g. "Fall", "Winter", "Spring", "Summer".
    name = Column(String(50), nullable=False)
    # Calendar year the term belongs to, e.g. 2026.
    year = Column(Integer, nullable=False)
    # Optional free-form note, e.g. "Week 6-10".
    description = Column(Text, nullable=True)
    # Optional planning window for the term. Purely informational: no scheduling
    # logic reads them, and either end may be left unset.
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = created_at_column()
    updated_at = updated_at_column()

    courses = relationship("Course", back_populates="term_record", lazy="dynamic")


class Course(Base):
    """Course / course offering within an organization.

    A course offering is identified by ``code`` + ``term`` + ``year`` so the
    same course can repeat across academic terms and be compared historically.

    ``term_id`` points at the organization-scoped :class:`Term` registry entry.
    It is nullable so pre-registry rows keep working; when set, ``term`` and
    ``year`` mirror the referenced term for the existing text-based queries.
    """

    __tablename__ = "courses"

    __table_args__ = (
        Index("idx_courses_organization_code", "organization_id", "code"),
        Index("idx_courses_term", "term_id"),
    )

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False
    )
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    # Academic term support.
    # ``term_id`` references the org-scoped terms registry; the text columns
    # below mirror it and remain authoritative for pre-registry courses.
    term_id = Column(UUID(as_uuid=False), ForeignKey("terms.id"), nullable=True)
    term = Column(String(50), nullable=True)  # e.g., "Fall 2024", "Winter 2025"
    year = Column(Integer, nullable=True)
    # Course analytics metadata
    department = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    settings = Column(JSONDict, default=dict)
    created_at = created_at_column()
    updated_at = updated_at_column()

    organization = relationship("Organization", back_populates="courses")
    assignments = relationship("Assignment", back_populates="course", lazy="dynamic")
    # Registry entry backing the term/year text columns, when one is linked.
    term_record = relationship("Term", back_populates="courses")
    instructors = relationship(
        "CourseInstructor", back_populates="course", lazy="dynamic", passive_deletes=True
    )
    # Student enrollments
    enrollments = relationship(
        "Enrollment", back_populates="course", lazy="dynamic", passive_deletes=True
    )


class Assignment(Base):
    """Assignment within a course.

    The ``assignment_type`` and flexible ``detection_config`` columns back the
    assignment-vulnerability analytics ("which assignment formats are most
    frequently copied?"). Other fields keep rich metadata without polluting the
    relational core with bespoke columns.
    """

    __tablename__ = "assignments"

    __table_args__ = (
        Index("idx_assignments_course_term", "course_id", "term"),
        Index("idx_assignments_type", "assignment_type"),
    )

    id = uuid_pk()
    course_id = Column(UUID(as_uuid=False), ForeignKey("courses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    term = Column(String(50), nullable=True)  # e.g., "Fall 2024", "Winter 2025"
    version = Column(Integer, default=1)  # Assignment version within course
    due_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Assignment analytics metadata
    assignment_type = Column(
        String(40), default="programming"
    )  # programming / written / project / quiz / exam
    description = Column(Text, nullable=True)
    max_score = Column(Float, nullable=True)
    team_mode = Column(String(20), default="individual")  # individual | group
    open_book = Column(Boolean, default=True)
    time_limited = Column(Boolean, default=False)
    allowed_resources = Column(JSONList, default=list)  # list[str]
    detection_config = Column(JSONDict, default=dict)
    settings = Column(JSONDict, default=dict)
    created_at = created_at_column()
    updated_at = updated_at_column()

    course = relationship("Course", back_populates="assignments")
    jobs = relationship("Job", back_populates="assignment", lazy="dynamic")
    # ``delete-orphan`` is required, not cosmetic: without it SQLAlchemy
    # "unlinks" children on parent delete by setting their FK to NULL, which
    # fails the NOT NULL constraint on assignment_versions.assignment_id.
    # ``passive_deletes`` lets the database-level ON DELETE CASCADE do the work.
    versions = relationship(
        "AssignmentVersion",
        back_populates="assignment",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Enrollment(Base):
    """Student enrollment in a course."""

    __tablename__ = "enrollments"

    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_enrollment"),
        Index("idx_enrollments_student", "student_id"),
    )

    id = uuid_pk()
    course_id = Column(
        UUID(as_uuid=False),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = Column(
        UUID(as_uuid=False),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    enrolled_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    role = Column(String(20), default="student")

    course = relationship("Course", back_populates="enrollments")
    student = relationship("Student", back_populates="enrollments")


class Student(Base):
    """Student profile (can exist across courses/terms)."""

    __tablename__ = "students"

    __table_args__ = (
        Index("idx_students_organization", "organization_id"),
        Index("idx_students_email", "email"),
        Index("idx_students_student_number", "student_number"),
    )

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=False
    )
    email = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    student_number = Column(String(50), nullable=True)
    settings = Column(JSONDict, default=dict)
    created_at = created_at_column()
    updated_at = updated_at_column()

    organization = relationship("Organization")
    enrollments = relationship("Enrollment", back_populates="student", passive_deletes=True)
    submissions = relationship("Submission", back_populates="student", lazy="dynamic")


class AssignmentVersion(Base):
    """Versioned assignment content for cross-semester comparison."""

    __tablename__ = "assignment_versions"

    __table_args__ = (
        # One row per (assignment, version). The API also checks this before
        # inserting, but the constraint makes concurrent creates safe.
        UniqueConstraint(
            "assignment_id", "version", name="uq_assignment_versions_assignment_version"
        ),
        Index("idx_assignment_versions_course", "course_id"),
    )

    id = uuid_pk()
    assignment_id = Column(
        UUID(as_uuid=False),
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id = Column(
        UUID(as_uuid=False),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(Integer, nullable=False, default=1, server_default=text("1"))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    starter_files = Column(JSONB, nullable=True)
    settings = Column(JSONDict, default=dict, server_default=text("'{}'::jsonb"))
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    is_active = Column(
        Boolean, default=True, server_default=text("TRUE"), nullable=False
    )

    assignment = relationship("Assignment", back_populates="versions")
    course = relationship("Course")


class CourseInstructor(Base):
    """Many-to-many association between courses and instructors (professors)."""

    __tablename__ = "course_instructors"

    id = uuid_pk()
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
    created_at = created_at_column()

    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_instructor"),
        Index("idx_course_instructors_user", "user_id"),
    )

    course = relationship("Course", back_populates="instructors")
    user = relationship("User", back_populates="courses")


class Case(Base):
    """Instructor review case for grouping similarity results."""

    __tablename__ = "cases"

    __table_args__ = (
        Index("idx_cases_assignment", "assignment_id"),
        Index("idx_cases_created_by", "created_by_id"),
        Index("idx_cases_status", "status"),
        Index("idx_cases_created_at", "created_at"),
        Index("idx_cases_org_created_at", "organization_id", "created_at"),
        Index("idx_cases_org_status", "organization_id", "status"),
        Index(
            "idx_cases_investigator",
            "investigator_id",
            postgresql_where=text("investigator_id IS NOT NULL"),
        ),
    )

    id = uuid_pk()
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
    created_at = created_at_column()
    updated_at = updated_at_column()
    closed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    organization = relationship("Organization")
    assignment = relationship("Assignment")
    investigator = relationship("User", foreign_keys=[investigator_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    result_links = relationship(
        "CaseResultLink", back_populates="case", lazy="dynamic", passive_deletes=True
    )
    comments = relationship(
        "CaseComment", back_populates="case", lazy="dynamic", passive_deletes=True
    )
    reports = relationship("Report", back_populates="case", passive_deletes=True)


class CaseResultLink(Base):
    """Link between a Case and a SimilarityResult."""

    __tablename__ = "case_result_links"

    __table_args__ = (
        # One link per (case, result). The unique constraint also serves lookups by case_id.
        UniqueConstraint("case_id", "similarity_result_id", name="uq_case_result_links_case_result"),
        Index("idx_case_result_links_similarity_result", "similarity_result_id"),
    )

    id = uuid_pk()
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    similarity_result_id = Column(
        UUID(as_uuid=False),
        ForeignKey("similarity_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = created_at_column()

    case = relationship("Case", back_populates="result_links")
    similarity_result = relationship("SimilarityResult")


class CaseComment(Base):
    """Comment on a review Case."""

    __tablename__ = "case_comments"

    __table_args__ = (
        Index("idx_case_comments_case", "case_id"),
        Index("idx_case_comments_user", "user_id"),
    )

    id = uuid_pk()
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = created_at_column()

    case = relationship("Case", back_populates="comments")
    user = relationship("User")


# ============================================================
# NEW MODELS - Added for production readiness
# ============================================================


class Report(Base):
    """Generated professional reports (PDF, HTML, JSON, etc.)."""

    __tablename__ = "reports"

    id = uuid_pk()
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(
        UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True
    )

    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True
    )
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)

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
    report_metadata = Column("metadata", JSONDict, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)

    created_at = created_at_column()
    updated_at = updated_at_column()

    __table_args__ = (
        Index("idx_reports_tenant_status", "tenant_id", "status"),
        Index("idx_reports_job", "job_id"),
        Index("idx_reports_case", "case_id"),
        Index("idx_reports_generated_at", "generated_at"),
        Index("idx_reports_tenant_type", "tenant_id", "report_type"),
        Index("idx_reports_organization", "organization_id", postgresql_where=text("organization_id IS NOT NULL")),
        Index("idx_reports_generated_by", "generated_by_user_id", postgresql_where=text("generated_by_user_id IS NOT NULL")),
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

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)

    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    related_job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True
    )
    related_case_id = Column(
        UUID(as_uuid=False), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    related_report_id = Column(
        UUID(as_uuid=False), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    channel = Column(String(20), nullable=False, default="in_app")
    priority = Column(String(20), nullable=False, default="normal")

    status = Column(String(20), nullable=False, default="pending")
    read_at = Column(TIMESTAMP(timezone=True), nullable=True)
    sent_at = Column(TIMESTAMP(timezone=True), nullable=True)

    payload = Column(JSONDict, nullable=False, default=dict)

    created_at = created_at_column()

    __table_args__ = (
        Index("idx_notifications_user_status", "user_id", "status"),
        Index("idx_notifications_tenant_created", "tenant_id", "created_at"),
        Index("idx_notifications_type", "type"),
        # Deleting a job, case or report scans notifications for rows to cascade to; without these that was a full
        # table scan per deleted row.
        Index("idx_notifications_related_job", "related_job_id", postgresql_where=text("related_job_id IS NOT NULL")),
        Index("idx_notifications_related_case", "related_case_id", postgresql_where=text("related_case_id IS NOT NULL")),
        Index("idx_notifications_related_report", "related_report_id", postgresql_where=text("related_report_id IS NOT NULL")),
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

    id = uuid_pk()
    submission_id = Column(
        UUID(as_uuid=False),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
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

    risk_score = Column(score_type(4, 3), nullable=True)
    patterns = Column(JSONDict, nullable=False, default=dict)

    created_at = created_at_column()

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

    id = uuid_pk()
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
    features = Column(JSONDict, nullable=False, default=dict)

    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)

    created_at = created_at_column()
    updated_at = updated_at_column()

    __table_args__ = (Index("idx_tenant_subscriptions_status", "status"),)

    # Relationships
    tenant = relationship("Tenant", back_populates="subscription")


class FprValidationRun(Base):
    """Stored Real FPR Validation runs for audit, comparison, and certification.

    These are professor/admin-initiated tests on known-clean student corpora
    to measure actual false positive risk before using the system in production courses.
    """

    __tablename__ = "fpr_validation_runs"

    id = uuid_pk()
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    payload = Column(JSONB, nullable=False)  # full result from /api/benchmark/real-fpr

    # Denormalized key metrics for fast filtering/listing without loading full payload
    num_submissions = Column(Integer, nullable=True)
    num_pairs = Column(Integer, nullable=True)
    mean_score = Column(score_type(5, 4), nullable=True)
    max_score = Column(score_type(5, 4), nullable=True)

    # Key decision values captured at the time of the run
    recommended_threshold = Column(score_type(5, 2), nullable=True)
    fpr_at_recommended_threshold = Column(score_type(6, 4), nullable=True)

    # User-provided notes and workflow status
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="completed")

    # Future-proofing for certification workflow
    is_certified = Column(Boolean, nullable=False, default=False)
    certified_by_user_id = Column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    certified_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = created_at_column()

    __table_args__ = (
        Index("idx_fpr_runs_tenant_created", "tenant_id", "created_at"),
        Index("idx_fpr_runs_user", "user_id"),
        Index("idx_fpr_runs_tenant_status", "tenant_id", "status"),
        Index("idx_fpr_runs_certified", "is_certified"),
        Index(
            "idx_fpr_runs_certified_by",
            "certified_by_user_id",
            postgresql_where=text("certified_by_user_id IS NOT NULL"),
        ),
    )

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User", foreign_keys=[user_id])
    certified_by = relationship("User", foreign_keys=[certified_by_user_id])


class TimelineEvent(Base):
    """Timeline event for investigation audit trail."""

    __tablename__ = "timeline_events"

    __table_args__ = (
        Index("idx_timeline_job", "job_id"),
        Index("idx_timeline_user", "user_id"),
        Index("idx_timeline_created_at", "created_at"),
        Index("idx_timeline_case_created", "case_id", "created_at"),
    )

    id = uuid_pk()
    case_id = Column(UUID(as_uuid=False), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True
    )
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    event_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_metadata = Column("metadata", JSONDict, nullable=False, default=dict)

    created_at = created_at_column()

    # Relationships
    case = relationship("Case")
    job = relationship("Job")
    user = relationship("User")


class PairReview(Base):
    """Faculty review decision (disposition) for a flagged submission pair.

    Rows are append-only: the latest row for a (job_id, submission_a,
    submission_b) triplet represents the current state; all prior rows are
    preserved for audit purposes.  Never UPDATE a row — INSERT a new one.

    Caveat: the appeal_* columns below can only be filled in by updating a row,
    which contradicts the rule above. Decide one way before the appeal workflow
    is switched on: either appeals insert a new row that copies the review, or
    appeals move to their own table.

    The ``ai_flag`` and ``corroborated`` fields capture the AI corroboration
    state *at the moment of review* so analytics remain accurate even if the
    policy thresholds are later changed.
    """

    __tablename__ = "pair_reviews"

    __table_args__ = (
        Index("idx_pair_reviews_job_band", "job_id", "band"),
        # Includes reviewed_at: the current state of a pair is its newest row, and this index answers
        # "latest review per pair" without a sort.
        Index(
            "idx_pair_reviews_job_pair",
            "job_id",
            "submission_a",
            "submission_b",
            "reviewed_at",
        ),
        Index("idx_pair_reviews_reviewer", "reviewer_id"),
        Index("idx_pair_reviews_reviewed_at", "reviewed_at"),
        Index("idx_pair_reviews_disposition", "disposition"),
        CheckConstraint(_in("band", PAIR_BANDS), name="ck_pair_reviews_band"),
        CheckConstraint(_in("disposition", PAIR_DISPOSITIONS), name="ck_pair_reviews_disposition"),
        CheckConstraint(_in("appeal_status", APPEAL_STATUSES), name="ck_pair_reviews_appeal_status"),
    )

    id = uuid_pk()

    # Which job and which pair
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    submission_a = Column(String(SUBMISSION_NAME_LENGTH), nullable=False)
    submission_b = Column(String(SUBMISSION_NAME_LENGTH), nullable=False)

    # Who reviewed and when
    reviewer_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    reviewed_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Computed band at review time: 'low' | 'review' | 'high'
    band = Column(String(16), nullable=False)

    # Faculty decision
    # Allowed values: no_action | note_on_file | conversation |
    #                 step_up_verification | formal_escalation
    disposition = Column(String(32), nullable=False)

    # Optional rationale (application layer enforces max 500 chars)
    rationale = Column(Text, nullable=True)

    # AI corroboration state captured at review time
    ai_flag = Column(Boolean, nullable=False, default=False)
    corroborated = Column(Boolean, nullable=False, default=False)

    # Similarity score recorded at review time (for analytics / overturn queries)
    similarity_score = Column(score_type(5, 4), nullable=True)

    # Appeal fields — nullable by design so no migration is needed when the
    # appeal workflow is activated.
    # Allowed appeal_status values: submitted | under_review | upheld | overturned
    appeal_status = Column(String(16), nullable=True)
    appeal_submitted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    appeal_outcome_at = Column(TIMESTAMP(timezone=True), nullable=True)
    appeal_notes = Column(Text, nullable=True)

    created_at = created_at_column()

    # Relationships
    job = relationship("Job")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class BandThreshold(Base):
    """Per-assignment-mode numeric thresholds for Low / Review / High bands.

    ``review_min`` is the lower edge of the Review band (anything below is Low).
    ``high_min``   is the lower edge of the High band.
    ``ai_elevated_min`` is the AI probability above which a score is "elevated".

    Rows are seeded by the migration and can be adjusted via direct DB update
    or a future admin UI, without requiring a code deployment.
    """

    __tablename__ = "band_thresholds"

    # assignment_mode is already unique (an index comes with that), so no separate index.
    # These rows are edited by hand ("direct DB update"), so the database refuses nonsense bands.
    __table_args__ = (
        CheckConstraint(
            "review_min >= 0 AND review_min < high_min AND high_min <= 1",
            name="ck_band_thresholds_band_order",
        ),
        CheckConstraint(
            "ai_elevated_min BETWEEN 0 AND 1 AND web_match_min BETWEEN 0 AND 1 AND engine_agree_min BETWEEN 0 AND 1",
            name="ck_band_thresholds_corroboration_range",
        ),
        CheckConstraint("engine_agree_count >= 1", name="ck_band_thresholds_engine_agree_count"),
    )

    id = uuid_pk()

    # Unique mode key — matches the assignment_mode field used across the codebase
    assignment_mode = Column(String(64), nullable=False, unique=True)

    # Band edges (0.0 – 1.0)
    review_min = Column(score_type(4, 3), nullable=False)
    high_min = Column(score_type(4, 3), nullable=False)

    # AI corroboration thresholds
    ai_elevated_min = Column(score_type(4, 3), nullable=False, default=0.650)
    web_match_min = Column(score_type(4, 3), nullable=False, default=0.700)

    # Engine-agreement corroboration: require this many engines to individually
    # score >= engine_agree_min before treating AI+similarity as corroborated.
    engine_agree_count = Column(Integer, nullable=False, default=2)
    engine_agree_min = Column(score_type(4, 3), nullable=False, default=0.500)

    created_at = created_at_column()
    updated_at = updated_at_column()
