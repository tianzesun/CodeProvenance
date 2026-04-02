"""Database models for IntegrityDesk multi-tenant system."""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime, 
    ForeignKey, JSON, UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.config.database import Base


class Tenant(Base):
    """Multi-tenant isolation model."""
    __tablename__ = "tenants"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), unique=True, nullable=False)
    tier = Column(String(50), default="free")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    jobs = relationship("Job", back_populates="tenant", lazy="dynamic")
    api_keys = relationship("ApiKey", back_populates="tenant", lazy="dynamic")


class ApiKey(Base):
    """API key management model."""
    __tablename__ = "api_keys"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    tenant = relationship("Tenant", back_populates="api_keys")


class Job(Base):
    """Analysis job model."""
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_tenant_status", "tenant_id", "status"),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")
    progress = Column(Integer, default=0)
    threshold = Column(Float, default=0.5)
    webhook_url = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    tenant = relationship("Tenant", back_populates="jobs")
    submissions = relationship("Submission", back_populates="job", lazy="dynamic")
    similarity_results = relationship("SimilarityResult", back_populates="job", lazy="dynamic")


class Submission(Base):
    """Code submission model."""
    __tablename__ = "submissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    file_count = Column(Integer, default=1)
    language_detected = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("Job", back_populates="submissions")


class SimilarityResult(Base):
    """Similarity analysis result model."""
    __tablename__ = "similarity_results"
    __table_args__ = (
        Index("idx_results_job_score", "job_id", "similarity_score"),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    submission_a_id = Column(String(36), nullable=False)
    submission_b_id = Column(String(36), nullable=False)
    similarity_score = Column(Float, nullable=False)
    confidence_lower = Column(Float, nullable=True)
    confidence_upper = Column(Float, nullable=True)
    detected_clones = Column(JSON, nullable=True)
    matching_blocks = Column(JSON, nullable=True)
    algorithm_scores = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("Job", back_populates="similarity_results")


class WebhookEvent(Base):
    """Webhook event tracking model."""
    __tablename__ = "webhook_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    payload = Column(JSON, nullable=True)
    signature = Column(String(255), nullable=True)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    last_error = Column(Text, nullable=True)
    next_attempt_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageMetric(Base):
    """Usage tracking model for metering."""
    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_usage_metrics_tenant_period"),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
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


class AuditLog(Base):
    """Audit log model for compliance."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_tenant_action", "tenant_id", "action"),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    user_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(36), nullable=True)
    changes = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)