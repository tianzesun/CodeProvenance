"""
SQLAlchemy models for CodeProvenance database.

This module defines all database models using SQLAlchemy ORM.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, BigInteger, Numeric, Boolean, Text, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class Tenant(Base):
    """
    Tenant model representing a client/SaaS platform.
    """
    __tablename__ = 'tenants'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(64), nullable=False, unique=True)
    tier = Column(String(20), nullable=False, default='free')
    status = Column(String(20), nullable=False, default='active')
    settings = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    trial_ends_at = Column(DateTime(timezone=True))
    monthly_job_limit = Column(Integer)
    concurrent_job_limit = Column(Integer)
    max_payload_mb = Column(Integer)
    rate_limit_per_minute = Column(Integer)
    
    # Relationships
    api_keys = relationship('ApiKey', back_populates='tenant', cascade='all, delete-orphan')
    jobs = relationship('Job', back_populates='tenant', cascade='all, delete-orphan')
    usage_metrics = relationship('UsageMetric', back_populates='tenant', cascade='all, delete-orphan')
    audit_logs = relationship('AuditLog', back_populates='tenant', cascade='all, delete-orphan')
    
    __table_args__ = (
        CheckConstraint("tier IN ('free', 'basic', 'pro', 'enterprise')", name='ck_tenants_tier'),
        CheckConstraint("status IN ('active', 'suspended', 'cancelled', 'trial')", name='ck_tenants_status'),
    )


class ApiKey(Base):
    """
    API Key model for tenant authentication.
    """
    __tablename__ = 'api_keys'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)
    name = Column(String(255))
    prefix = Column(String(12), nullable=False)
    permissions = Column(JSONB, default=['read', 'write'])
    rate_limit_override = Column(Integer)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship('Tenant', back_populates='api_keys')


class Job(Base):
    """
    Job model representing a similarity analysis request.
    """
    __tablename__ = 'jobs'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default='queued')
    threshold = Column(Numeric(3, 2), nullable=False, default=0.7)
    webhook_url = Column(Text)
    idempotency_key = Column(String(255), unique=True)
    retention_days = Column(Integer, nullable=False, default=90)
    detection_modes = Column(JSONB, nullable=False, default=['token', 'ast', 'ngram'])
    language_filters = Column(JSONB)
    exclude_patterns = Column(JSONB, default=['__pycache__', '*.class', 'node_modules'])
    template_files = Column(JSONB, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    total_submissions = Column(Integer, default=0)
    total_pairs_analyzed = Column(Integer, default=0)
    high_similarity_count = Column(Integer, default=0)
    settings = Column(JSONB, default={})
    
    # Relationships
    tenant = relationship('Tenant', back_populates='jobs')
    submissions = relationship('Submission', back_populates='job', cascade='all, delete-orphan')
    similarity_results = relationship('SimilarityResult', back_populates='job', cascade='all, delete-orphan')
    webhook_events = relationship('WebhookEvent', back_populates='job', cascade='all, delete-orphan')
    
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')", name='ck_jobs_status'),
        CheckConstraint("threshold >= 0 AND threshold <= 1", name='ck_jobs_threshold'),
    )


class Submission(Base):
    """
    Submission model representing individual student submissions within a job.
    """
    __tablename__ = 'submissions'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    external_id = Column(String(255))
    file_count = Column(Integer, nullable=False, default=0)
    total_size_bytes = Column(BigInteger, default=0)
    file_paths = Column(JSONB, nullable=False)
    language_detected = Column(String(50))
    languages_detected = Column(JSONB)
    storage_path = Column(String(500))
    checksum = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    processing_error = Column(Text)
    
    # Relationships
    job = relationship('Job', back_populates='submissions')
    similarity_results_a = relationship('SimilarityResult', foreign_keys='SimilarityResult.submission_a_id', back_populates='submission_a')
    similarity_results_b = relationship('SimilarityResult', foreign_keys='SimilarityResult.submission_b_id', back_populates='submission_b')


class SimilarityResult(Base):
    """
    Similarity Result model representing pairwise comparison results.
    """
    __tablename__ = 'similarity_results'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    submission_a_id = Column(UUID, ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False)
    submission_b_id = Column(UUID, ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False)
    similarity_score = Column(Numeric(5, 4), nullable=False)
    confidence_lower = Column(Numeric(5, 4), nullable=False)
    confidence_upper = Column(Numeric(5, 4), nullable=False)
    confidence_level = Column(Numeric(3, 2), default=0.95)
    matching_blocks = Column(JSONB, nullable=False, default=[])
    excluded_matches = Column(JSONB, default=[])
    algorithm_scores = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job = relationship('Job', back_populates='similarity_results')
    submission_a = relationship('Submission', foreign_keys=[submission_a_id], back_populates='similarity_results_a')
    submission_b = relationship('Submission', foreign_keys=[submission_b_id], back_populates='similarity_results_b')
    
    __table_args__ = (
        CheckConstraint("similarity_score >= 0 AND similarity_score <= 1", name='ck_similarity_results_score'),
        CheckConstraint("confidence_level > 0 AND confidence_level <= 1", name='ck_similarity_results_confidence'),
        CheckConstraint("submission_a_id < submission_b_id", name='ck_no_duplicate_pairs'),
    )


class WebhookEvent(Base):
    """
    Webhook Event model for tracking webhook delivery attempts.
    """
    __tablename__ = 'webhook_events'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    next_attempt_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    signature = Column(String(128))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job = relationship('Job', back_populates='webhook_events')
    
    __table_args__ = (
        CheckConstraint("event_type IN ('job.completed', 'job.failed', 'job.progress')", name='ck_webhook_events_type'),
        CheckConstraint("status IN ('pending', 'delivered', 'failed', 'retried')", name='ck_webhook_events_status'),
    )


class UsageMetric(Base):
    """
    Usage Metric model for billing and analytics.
    """
    __tablename__ = 'usage_metrics'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(7), nullable=False)  # Format: YYYY-MM
    jobs_processed = Column(Integer, default=0)
    jobs_successful = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    files_parsed = Column(Integer, default=0)
    total_size_mb = Column(Numeric(10, 2), default=0)
    compute_seconds = Column(Numeric(10, 2), default=0)
    api_calls = Column(Integer, default=0)
    webhook_attempts = Column(Integer, default=0)
    webhook_deliveries = Column(Integer, default=0)
    peak_concurrent_jobs = Column(Integer, default=0)
    storage_used_mb = Column(Numeric(10, 2), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship('Tenant', back_populates='usage_metrics')
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'period', name='uq_usage_metrics_tenant_period'),
    )


class AuditLog(Base):
    """
    Audit Log model for compliance and debugging.
    """
    __tablename__ = 'audit_logs'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey('tenants.id', ondelete='SET NULL'))
    job_id = Column(UUID, ForeignKey('jobs.id', ondelete='SET NULL'))
    user_id = Column(UUID)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(UUID)
    changes = Column(JSONB)
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tenant = relationship('Tenant', back_populates='audit_logs')
