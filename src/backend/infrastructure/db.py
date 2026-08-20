"""
Database utility layer for IntegrityDesk.

This module provides high-level database operations and helper functions
for common database tasks.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.backend.config.settings import settings
from src.backend.models.database import (
    Assignment,
    AuditLog,
    Course,
    Job,
    SimilarityResult,
    Submission,
    Tenant,
    UsageMetric,
    WebhookEvent,
)


class TenantService:
    """
    Service class for tenant-related database operations.
    """

    @staticmethod
    def create_tenant(
        db: Session, name: str, api_key_hash: str, tier: str = "free"
    ) -> Tenant:
        """
        Create a new tenant.

        Args:
            db: Database session
            name: Tenant name
            api_key_hash: Hashed API key
            tier: Subscription tier

        Returns:
            Created Tenant instance
        """
        tenant = Tenant(name=name, api_key_hash=api_key_hash, tier=tier)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def get_tenant_by_api_key(db: Session, api_key_hash: str) -> Tenant | None:
        """
        Get tenant by API key hash.

        Args:
            db: Database session
            api_key_hash: Hashed API key

        Returns:
            Tenant instance or None
        """
        return db.query(Tenant).filter(Tenant.api_key_hash == api_key_hash).first()

    @staticmethod
    def get_tenant_by_id(db: Session, tenant_id: str) -> Tenant | None:
        """
        Get tenant by ID.

        Args:
            db: Database session
            tenant_id: Tenant UUID

        Returns:
            Tenant instance or None
        """
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()


class JobService:
    """
    Service class for job-related database operations.
    """

    @staticmethod
    def create_job(
        db: Session,
        tenant_id: str,
        name: str,
        assignment_id: str | None = None,  # NEW: link to normalized Assignment
        threshold: float = 0.7,
        webhook_url: str | None = None,
        idempotency_key: str | None = None,
        detection_modes: list[str] | None = None,
        language_filters: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        template_files: list[dict[str, Any]] | None = None,
        retention_days: int = 90,
    ) -> Job:
        """
        Create a new job.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            name: Job name
            threshold: Similarity threshold (0.0 to 1.0)
            webhook_url: Optional webhook URL for notifications
            idempotency_key: Optional idempotency key
            detection_modes: List of detection algorithms to use
            language_filters: Optional list of languages to filter
            exclude_patterns: Optional list of patterns to exclude
            template_files: Optional list of template files
            retention_days: Number of days to retain data

        Returns:
            Created Job instance
        """
        job = Job(
            tenant_id=tenant_id,
            assignment_id=assignment_id,  # NEW
            name=name,
            threshold=threshold,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
            detection_modes=detection_modes or list(settings.DEFAULT_DETECTION_MODES),
            language_filters=language_filters,
            exclude_patterns=exclude_patterns
            or ["__pycache__", "*.class", "node_modules"],
            template_files=template_files or [],
            retention_days=retention_days,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_job_by_id(db: Session, job_id: str, tenant_id: str) -> Job | None:
        """
        Get job by ID with tenant isolation.

        Args:
            db: Database session
            job_id: Job UUID
            tenant_id: Tenant UUID

        Returns:
            Job instance or None
        """
        return (
            db.query(Job)
            .filter(and_(Job.id == job_id, Job.tenant_id == tenant_id))
            .first()
        )

    @staticmethod
    def get_jobs_by_tenant(
        db: Session,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        """
        Get jobs for a tenant with optional status filter.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            status: Optional status filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of Job instances
        """
        query = db.query(Job).filter(Job.tenant_id == tenant_id)

        if status:
            query = query.filter(Job.status == status)

        return query.order_by(Job.created_at.desc()).limit(limit).offset(offset).all()

    @staticmethod
    def update_job_status(
        db: Session, job_id: str, status: str, error_message: str | None = None
    ) -> Job | None:
        """
        Update job status.

        Args:
            db: Database session
            job_id: Job UUID
            status: New status
            error_message: Optional error message

        Returns:
            Updated Job instance or None
        """
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None

        job.status = status

        if status == "processing":
            job.started_at = datetime.utcnow()
        elif status == "completed":
            job.completed_at = datetime.utcnow()
            if job.started_at:
                job.execution_time_ms = int(
                    (job.completed_at - job.started_at).total_seconds() * 1000
                )
        elif status == "failed":
            job.failed_at = datetime.utcnow()
            job.error_message = error_message

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def check_idempotency_key(db: Session, idempotency_key: str) -> Job | None:
        """
        Check if an idempotency key already exists.

        Args:
            db: Database session
            idempotency_key: Idempotency key to check

        Returns:
            Existing Job instance or None
        """
        return db.query(Job).filter(Job.idempotency_key == idempotency_key).first()


class SubmissionService:
    """
    Service class for submission-related database operations.
    """

    @staticmethod
    def create_submission(
        db: Session,
        job_id: str,
        name: str,
        file_paths: list[str],
        external_id: str | None = None,
        language_detected: str | None = None,
        languages_detected: list[str] | None = None,
        storage_path: str | None = None,
        checksum: str | None = None,
    ) -> Submission:
        """
        Create a new submission.

        Args:
            db: Database session
            job_id: Job UUID
            name: Submission name
            file_paths: List of file paths
            external_id: Optional external ID
            language_detected: Optional detected language
            languages_detected: Optional list of detected languages
            storage_path: Optional storage path
            checksum: Optional file checksum

        Returns:
            Created Submission instance
        """
        submission = Submission(
            job_id=job_id,
            name=name,
            file_paths=file_paths,
            external_id=external_id,
            file_count=len(file_paths),
            language_detected=language_detected,
            languages_detected=languages_detected,
            storage_path=storage_path,
            checksum=checksum,
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        return submission

    @staticmethod
    def get_submissions_by_job(db: Session, job_id: str) -> list[Submission]:
        """
        Get all submissions for a job.

        Args:
            db: Database session
            job_id: Job UUID

        Returns:
            List of Submission instances
        """
        return db.query(Submission).filter(Submission.job_id == job_id).all()


class SimilarityResultService:
    """
    Service class for similarity result-related database operations.
    """

    @staticmethod
    def create_similarity_result(
        db: Session,
        job_id: str,
        submission_a_id: str,
        submission_b_id: str,
        similarity_score: float,
        confidence_lower: float,
        confidence_upper: float,
        matching_blocks: list[dict[str, Any]],
        excluded_matches: list[dict[str, Any]] | None = None,
        algorithm_scores: dict[str, float] | None = None,
        verdict: str | None = None,
    ) -> SimilarityResult:
        """
        Create a new similarity result.

        Args:
            db: Database session
            job_id: Job UUID
            submission_a_id: First submission UUID
            submission_b_id: Second submission UUID
            similarity_score: Similarity score (0.0 to 1.0)
            confidence_lower: Lower confidence bound
            confidence_upper: Upper confidence bound
            matching_blocks: List of matching blocks
            excluded_matches: Optional list of excluded matches
            algorithm_scores: Optional dictionary of algorithm scores
            verdict: Optional rule-based verdict (TRUE, PROBABLE, REVIEW, FLAG, CLEAN)

        Returns:
            Created SimilarityResult instance
        """
        # Ensure submission_a_id < submission_b_id to avoid duplicates
        if submission_a_id > submission_b_id:
            submission_a_id, submission_b_id = submission_b_id, submission_a_id

        result = SimilarityResult(
            job_id=job_id,
            submission_a_id=submission_a_id,
            submission_b_id=submission_b_id,
            similarity_score=similarity_score,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            matching_blocks=matching_blocks,
            excluded_matches=excluded_matches or [],
            algorithm_scores=algorithm_scores,
            verdict=verdict,
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    @staticmethod
    def get_results_by_job(
        db: Session,
        job_id: str,
        threshold: float | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[SimilarityResult]:
        """
        Get similarity results for a job.

        Args:
            db: Database session
            job_id: Job UUID
            threshold: Optional minimum similarity threshold
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of SimilarityResult instances
        """
        query = db.query(SimilarityResult).filter(SimilarityResult.job_id == job_id)

        if threshold is not None:
            query = query.filter(SimilarityResult.similarity_score >= threshold)

        return (
            query.order_by(SimilarityResult.similarity_score.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )


class WebhookEventService:
    """
    Service class for webhook event-related database operations.
    """

    @staticmethod
    def create_webhook_event(
        db: Session,
        job_id: str,
        event_type: str,
        payload: dict[str, Any],
        signature: str | None = None,
    ) -> WebhookEvent:
        """
        Create a new webhook event.

        Args:
            db: Database session
            job_id: Job UUID
            event_type: Event type (job.completed, job.failed, job.progress)
            payload: Event payload
            signature: Optional HMAC signature

        Returns:
            Created WebhookEvent instance
        """
        event = WebhookEvent(
            job_id=job_id, event_type=event_type, payload=payload, signature=signature
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_pending_webhook_events(db: Session, limit: int = 100) -> list[WebhookEvent]:
        """
        Get pending webhook events for delivery.

        Args:
            db: Database session
            limit: Maximum number of events

        Returns:
            List of WebhookEvent instances
        """
        now = datetime.utcnow()
        return (
            db.query(WebhookEvent)
            .filter(
                and_(
                    or_(
                        WebhookEvent.status == "pending",
                        and_(
                            WebhookEvent.status == "failed",
                            WebhookEvent.next_attempt_at <= now,
                        ),
                    ),
                    WebhookEvent.attempt_count < WebhookEvent.max_attempts,
                )
            )
            .order_by(WebhookEvent.created_at)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_webhook_event_status(
        db: Session, event_id: str, status: str, error_message: str | None = None
    ) -> WebhookEvent | None:
        """
        Update webhook event status.

        Args:
            db: Database session
            event_id: Webhook event UUID
            status: New status
            error_message: Optional error message

        Returns:
            Updated WebhookEvent instance or None
        """
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if not event:
            return None

        event.status = status
        event.attempt_count += 1

        if status == "delivered":
            event.delivered_at = datetime.utcnow()
        elif status == "failed":
            event.last_error = error_message
            # Calculate next retry with exponential backoff
            backoff_seconds = 60 * (2**event.attempt_count)
            event.next_attempt_at = datetime.utcnow() + timedelta(
                seconds=backoff_seconds
            )

        db.commit()
        db.refresh(event)
        return event


class UsageMetricService:
    """
    Service class for usage metric-related database operations.
    """

    @staticmethod
    def get_or_create_usage_metric(
        db: Session, tenant_id: str, period: str
    ) -> UsageMetric:
        """
        Get or create usage metric for a tenant and period.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            period: Period in YYYY-MM format

        Returns:
            UsageMetric instance
        """
        metric = (
            db.query(UsageMetric)
            .filter(
                and_(UsageMetric.tenant_id == tenant_id, UsageMetric.period == period)
            )
            .first()
        )

        if not metric:
            metric = UsageMetric(tenant_id=tenant_id, period=period)
            db.add(metric)
            db.commit()
            db.refresh(metric)

        return metric

    @staticmethod
    def increment_usage(
        db: Session,
        tenant_id: str,
        jobs_processed: int = 0,
        jobs_successful: int = 0,
        jobs_failed: int = 0,
        files_parsed: int = 0,
        total_size_mb: float = 0,
        compute_seconds: float = 0,
        api_calls: int = 0,
        webhook_attempts: int = 0,
        webhook_deliveries: int = 0,
    ) -> UsageMetric:
        """
        Increment usage metrics for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            jobs_processed: Number of jobs processed
            jobs_successful: Number of successful jobs
            jobs_failed: Number of failed jobs
            files_parsed: Number of files parsed
            total_size_mb: Total size in MB
            compute_seconds: Compute time in seconds
            api_calls: Number of API calls
            webhook_attempts: Number of webhook attempts
            webhook_deliveries: Number of successful webhook deliveries

        Returns:
            Updated UsageMetric instance
        """
        period = datetime.utcnow().strftime("%Y-%m")
        metric = UsageMetricService.get_or_create_usage_metric(db, tenant_id, period)

        metric.jobs_processed += jobs_processed
        metric.jobs_successful += jobs_successful
        metric.jobs_failed += jobs_failed
        metric.files_parsed += files_parsed
        metric.total_size_mb += total_size_mb
        metric.compute_seconds += compute_seconds
        metric.api_calls += api_calls
        metric.webhook_attempts += webhook_attempts
        metric.webhook_deliveries += webhook_deliveries

        db.commit()
        db.refresh(metric)
        return metric


class AuditLogService:
    """
    Service class for audit log-related database operations.
    """

    @staticmethod
    def create_audit_log(
        db: Session,
        action: str,
        tenant_id: str | None = None,
        job_id: str | None = None,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        changes: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Create a new audit log entry.

        Args:
            db: Database session
            action: Action performed
            tenant_id: Optional tenant UUID
            job_id: Optional job UUID
            user_id: Optional user UUID
            resource_type: Optional resource type
            resource_id: Optional resource UUID
            changes: Optional changes dictionary
            ip_address: Optional IP address
            user_agent: Optional user agent

        Returns:
            Created AuditLog instance
        """
        log = AuditLog(
            action=action,
            tenant_id=tenant_id,
            job_id=job_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log


class AcademicService:
    """
    Service for resolving/creating academic entities (Course, Assignment)
    from free-text names provided during upload/analysis. This bridges the
    legacy string-based flow with the new normalized schema.
    """

    @staticmethod
    def get_or_create_assignment(
        db: Session,
        tenant_id: str,
        course_name: str,
        assignment_name: str,
        assignment_mode: str | None = None,
    ) -> Assignment:
        """
        Get or create a Course + Assignment for the given tenant based on names.
        Used during upload to wire the new schema.
        """
        if not course_name:
            course_name = "Unnamed Course"
        if not assignment_name:
            assignment_name = course_name

        # Find or create Course
        course = (
            db.query(Course)
            .filter(Course.tenant_id == tenant_id, Course.name == course_name)
            .first()
        )

        if not course:
            course = Course(
                tenant_id=tenant_id,
                name=course_name,
            )
            db.add(course)
            db.flush()

        # Find or create Assignment under the Course
        assignment = (
            db.query(Assignment)
            .filter(
                Assignment.tenant_id == tenant_id,
                Assignment.course_id == course.id,
                Assignment.name == assignment_name,
            )
            .first()
        )

        if not assignment:
            assignment = Assignment(
                tenant_id=tenant_id,
                course_id=course.id,
                name=assignment_name,
                assignment_mode=assignment_mode,
            )
            db.add(assignment)
            db.flush()

        db.commit()
        db.refresh(assignment)
        return assignment
