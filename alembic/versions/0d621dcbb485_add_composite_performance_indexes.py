"""add_composite_performance_indexes

Revision ID: 0d621dcbb485
Revises: 2885d0f9202c
Create Date: 2026-05-23 14:47:21.809503

Adds composite indexes for the most common multi-column query patterns,
especially tenant/organization + time or status filters. These provide
significant performance gains for dashboard and review workloads.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d621dcbb485'
down_revision = '2885d0f9202c'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Jobs - very common "my recent jobs" per tenant
    op.create_index('idx_jobs_tenant_created_at', 'jobs', ['tenant_id', 'created_at'])

    # Cases - org-scoped case dashboards
    op.create_index('idx_cases_org_created_at', 'cases', ['organization_id', 'created_at'])
    op.create_index('idx_cases_org_status', 'cases', ['organization_id', 'status'])

    # Similarity results - per-job review workflows
    # We must ensure the column exists before creating a composite index on it
    op.execute("""
        ALTER TABLE similarity_results 
        ADD COLUMN IF NOT EXISTS review_status VARCHAR(50)
    """)
    op.create_index('idx_similarity_results_job_review', 'similarity_results', ['job_id', 'review_status'])

    # Audit logs - tenant audit history over time
    op.create_index('idx_audit_logs_tenant_created_at', 'audit_logs', ['tenant_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_audit_logs_tenant_created_at', table_name='audit_logs')
    op.drop_index('idx_similarity_results_job_review', table_name='similarity_results')
    op.drop_index('idx_cases_org_status', table_name='cases')
    op.drop_index('idx_cases_org_created_at', table_name='cases')
    op.drop_index('idx_jobs_tenant_created_at', table_name='jobs')
