"""
Initial schema for CodeProvenance database.

Revision ID: 001
Revises: 
Create Date: 2026-03-27

This migration creates the initial database schema including:
- tenants table
- api_keys table
- jobs table
- submissions table
- similarity_results table
- webhook_events table
- usage_metrics table
- audit_logs table
- Row-Level Security (RLS) policies for multi-tenancy
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create all initial tables and indexes.
    """
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('api_key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('tier', sa.String(20), nullable=False, server_default='free'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('settings', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True)),
        sa.Column('monthly_job_limit', sa.Integer),
        sa.Column('concurrent_job_limit', sa.Integer),
        sa.Column('max_payload_mb', sa.Integer),
        sa.Column('rate_limit_per_minute', sa.Integer),
        sa.CheckConstraint("tier IN ('free', 'basic', 'pro', 'enterprise')", name='ck_tenants_tier'),
        sa.CheckConstraint("status IN ('active', 'suspended', 'cancelled', 'trial')", name='ck_tenants_status')
    )
    
    # Create indexes for tenants
    op.create_index('idx_tenants_api_key_hash', 'tenants', ['api_key_hash'])
    op.create_index('idx_tenants_status', 'tenants', ['status'])
    op.create_index('idx_tenants_tier', 'tenants', ['tier'])
    
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('name', sa.String(255)),
        sa.Column('prefix', sa.String(12), nullable=False),
        sa.Column('permissions', JSONB, server_default='["read", "write"]'),
        sa.Column('rate_limit_override', sa.Integer),
        sa.Column('is_active', sa.Boolean, server_default='TRUE'),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )
    
    # Create indexes for api_keys
    op.create_index('idx_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    op.create_index('idx_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index('idx_api_keys_prefix', 'api_keys', ['prefix'])
    op.create_index('idx_api_keys_active', 'api_keys', ['is_active'], postgresql_where=sa.text('is_active = TRUE'))
    
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('threshold', sa.Numeric(3, 2), nullable=False, server_default='0.7'),
        sa.Column('webhook_url', sa.Text),
        sa.Column('idempotency_key', sa.String(255), unique=True),
        sa.Column('retention_days', sa.Integer, nullable=False, server_default='90'),
        sa.Column('detection_modes', JSONB, nullable=False, server_default='["token", "ast", "ngram"]'),
        sa.Column('language_filters', JSONB),
        sa.Column('exclude_patterns', JSONB, server_default='["__pycache__", "*.class", "node_modules"]'),
        sa.Column('template_files', JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('failed_at', sa.DateTime(timezone=True)),
        sa.Column('error_message', sa.Text),
        sa.Column('execution_time_ms', sa.Integer),
        sa.Column('total_submissions', sa.Integer, server_default='0'),
        sa.Column('total_pairs_analyzed', sa.Integer, server_default='0'),
        sa.Column('high_similarity_count', sa.Integer, server_default='0'),
        sa.Column('settings', JSONB, server_default='{}'),
        sa.CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')", name='ck_jobs_status'),
        sa.CheckConstraint("threshold >= 0 AND threshold <= 1", name='ck_jobs_threshold')
    )
    
    # Create indexes for jobs
    op.create_index('idx_jobs_tenant_id', 'jobs', ['tenant_id'])
    op.create_index('idx_jobs_status', 'jobs', ['status'])
    op.create_index('idx_jobs_created_at', 'jobs', ['created_at'])
    op.create_index('idx_jobs_idempotency_key', 'jobs', ['idempotency_key'], postgresql_where=sa.text('idempotency_key IS NOT NULL'))
    op.create_index('idx_jobs_webhook_url', 'jobs', ['webhook_url'], postgresql_where=sa.text('webhook_url IS NOT NULL'))
    op.create_index('idx_jobs_tenant_status', 'jobs', ['tenant_id', 'status'])
    
    # Create submissions table
    op.create_table(
        'submissions',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', UUID, sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('external_id', sa.String(255)),
        sa.Column('file_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_size_bytes', sa.BigInteger, server_default='0'),
        sa.Column('file_paths', JSONB, nullable=False),
        sa.Column('language_detected', sa.String(50)),
        sa.Column('languages_detected', JSONB),
        sa.Column('storage_path', sa.String(500)),
        sa.Column('checksum', sa.String(64)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.Column('processing_error', sa.Text)
    )
    
    # Create indexes for submissions
    op.create_index('idx_submissions_job_id', 'submissions', ['job_id'])
    op.create_index('idx_submissions_name', 'submissions', ['name'])
    op.create_index('idx_submissions_external_id', 'submissions', ['external_id'])
    op.create_index('idx_submissions_language', 'submissions', ['language_detected'])
    op.create_index('idx_submissions_job_name', 'submissions', ['job_id', 'name'])
    
    # Create similarity_results table
    op.create_table(
        'similarity_results',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', UUID, sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('submission_a_id', UUID, sa.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('submission_b_id', UUID, sa.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('similarity_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('confidence_lower', sa.Numeric(5, 4), nullable=False),
        sa.Column('confidence_upper', sa.Numeric(5, 4), nullable=False),
        sa.Column('confidence_level', sa.Numeric(3, 2), server_default='0.95'),
        sa.Column('matching_blocks', JSONB, nullable=False, server_default='[]'),
        sa.Column('excluded_matches', JSONB, server_default='[]'),
        sa.Column('algorithm_scores', JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.CheckConstraint("similarity_score >= 0 AND similarity_score <= 1", name='ck_similarity_results_score'),
        sa.CheckConstraint("confidence_level > 0 AND confidence_level <= 1", name='ck_similarity_results_confidence'),
        sa.CheckConstraint("submission_a_id < submission_b_id", name='ck_no_duplicate_pairs')
    )
    
    # Create indexes for similarity_results
    op.create_index('idx_similarity_results_job_id', 'similarity_results', ['job_id'])
    op.create_index('idx_similarity_results_submission_a', 'similarity_results', ['submission_a_id'])
    op.create_index('idx_similarity_results_submission_b', 'similarity_results', ['submission_b_id'])
    op.create_index('idx_similarity_results_score', 'similarity_results', ['similarity_score'], postgresql_ops={'similarity_score': 'DESC'})
    op.create_index('idx_similarity_results_job_score', 'similarity_results', ['job_id', 'similarity_score'], postgresql_ops={'similarity_score': 'DESC'})
    op.create_index('idx_similarity_results_submissions', 'similarity_results', ['submission_a_id', 'submission_b_id'])
    op.create_index(
        'idx_similarity_results_high_similarity',
        'similarity_results',
        ['job_id', 'similarity_score'],
        postgresql_where=sa.text('similarity_score >= 0.7')
    )
    
    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', UUID, sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('attempt_count', sa.Integer, server_default='0'),
        sa.Column('max_attempts', sa.Integer, server_default='3'),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True)),
        sa.Column('delivered_at', sa.DateTime(timezone=True)),
        sa.Column('last_error', sa.Text),
        sa.Column('signature', sa.String(128)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.CheckConstraint("event_type IN ('job.completed', 'job.failed', 'job.progress')", name='ck_webhook_events_type'),
        sa.CheckConstraint("status IN ('pending', 'delivered', 'failed', 'retried')", name='ck_webhook_events_status')
    )
    
    # Create indexes for webhook_events
    op.create_index('idx_webhook_events_job_id', 'webhook_events', ['job_id'])
    op.create_index('idx_webhook_events_status', 'webhook_events', ['status'])
    op.create_index(
        'idx_webhook_events_next_attempt',
        'webhook_events',
        ['next_attempt_at'],
        postgresql_where=sa.text("status IN ('pending', 'failed')")
    )
    op.create_index('idx_webhook_events_job_type', 'webhook_events', ['job_id', 'event_type'])
    
    # Create usage_metrics table
    op.create_table(
        'usage_metrics',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period', sa.String(7), nullable=False),
        sa.Column('jobs_processed', sa.Integer, server_default='0'),
        sa.Column('jobs_successful', sa.Integer, server_default='0'),
        sa.Column('jobs_failed', sa.Integer, server_default='0'),
        sa.Column('files_parsed', sa.Integer, server_default='0'),
        sa.Column('total_size_mb', sa.Numeric(10, 2), server_default='0'),
        sa.Column('compute_seconds', sa.Numeric(10, 2), server_default='0'),
        sa.Column('api_calls', sa.Integer, server_default='0'),
        sa.Column('webhook_attempts', sa.Integer, server_default='0'),
        sa.Column('webhook_deliveries', sa.Integer, server_default='0'),
        sa.Column('peak_concurrent_jobs', sa.Integer, server_default='0'),
        sa.Column('storage_used_mb', sa.Numeric(10, 2), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('tenant_id', 'period', name='uq_usage_metrics_tenant_period')
    )
    
    # Create indexes for usage_metrics
    op.create_index('idx_usage_metrics_tenant_id', 'usage_metrics', ['tenant_id'])
    op.create_index('idx_usage_metrics_period', 'usage_metrics', ['period'])
    op.create_index('idx_usage_metrics_tenant_period', 'usage_metrics', ['tenant_id', 'period'])
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='SET NULL')),
        sa.Column('job_id', UUID, sa.ForeignKey('jobs.id', ondelete='SET NULL')),
        sa.Column('user_id', UUID),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50)),
        sa.Column('resource_id', UUID),
        sa.Column('changes', JSONB),
        sa.Column('ip_address', INET),
        sa.Column('user_agent', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )
    
    # Create indexes for audit_logs
    op.create_index('idx_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('idx_audit_logs_job_id', 'audit_logs', ['job_id'])
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('idx_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])
    
    # Enable Row-Level Security on all tables
    op.execute('ALTER TABLE tenants ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE jobs ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE submissions ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE similarity_results ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE usage_metrics ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY')
    
    # Create RLS policies for tenant isolation
    # Note: These policies assume the application sets app.current_tenant_id
    # before executing queries. This is done in the database utility layer.
    
    op.execute("""
        CREATE POLICY tenant_own_tenant ON tenants
        FOR ALL USING (id = current_setting('app.current_tenant_id', TRUE)::uuid)
    """)
    
    op.execute("""
        CREATE POLICY api_keys_tenant_access ON api_keys
        FOR ALL USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid)
    """)
    
    op.execute("""
        CREATE POLICY jobs_tenant_access ON jobs
        FOR ALL USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid)
    """)
    
    op.execute("""
        CREATE POLICY submissions_tenant_access ON submissions
        FOR ALL USING (job_id IN (
            SELECT id FROM jobs WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid
        ))
    """)
    
    op.execute("""
        CREATE POLICY similarity_results_tenant_access ON similarity_results
        FOR ALL USING (job_id IN (
            SELECT id FROM jobs WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid
        ))
    """)
    
    op.execute("""
        CREATE POLICY webhook_events_tenant_access ON webhook_events
        FOR ALL USING (job_id IN (
            SELECT id FROM jobs WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid
        ))
    """)
    
    op.execute("""
        CREATE POLICY usage_metrics_tenant_access ON usage_metrics
        FOR ALL USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid)
    """)
    
    op.execute("""
        CREATE POLICY audit_logs_tenant_access ON audit_logs
        FOR ALL USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid)
    """)


def downgrade() -> None:
    """
    Drop all tables and indexes.
    """
    # Drop RLS policies
    op.execute('DROP POLICY IF EXISTS tenant_own_tenant ON tenants')
    op.execute('DROP POLICY IF EXISTS api_keys_tenant_access ON api_keys')
    op.execute('DROP POLICY IF EXISTS jobs_tenant_access ON jobs')
    op.execute('DROP POLICY IF EXISTS submissions_tenant_access ON submissions')
    op.execute('DROP POLICY IF EXISTS similarity_results_tenant_access ON similarity_results')
    op.execute('DROP POLICY IF EXISTS webhook_events_tenant_access ON webhook_events')
    op.execute('DROP POLICY IF EXISTS usage_metrics_tenant_access ON usage_metrics')
    op.execute('DROP POLICY IF EXISTS audit_logs_tenant_access ON audit_logs')
    
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('audit_logs')
    op.drop_table('usage_metrics')
    op.drop_table('webhook_events')
    op.drop_table('similarity_results')
    op.drop_table('submissions')
    op.drop_table('jobs')
    op.drop_table('api_keys')
    op.drop_table('tenants')
