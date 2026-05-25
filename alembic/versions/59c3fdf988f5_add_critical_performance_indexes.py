"""add_critical_performance_indexes

Revision ID: 59c3fdf988f5
Revises: b2c3d4e5f6a7
Create Date: 2026-05-23 14:31:05.536432

Adds critical missing indexes on high-traffic foreign keys and filter columns
identified as performance hotspots (especially for multi-tenant queries,
job processing, review workflows, and the new Organization/Course features).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '59c3fdf988f5'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS so the migration is safe
    # even if some indexes were created manually or in previous runs.

    op.execute("CREATE INDEX IF NOT EXISTS idx_submissions_job ON submissions (job_id)")

    # courses & assignments
    op.execute("CREATE INDEX IF NOT EXISTS idx_courses_organization ON courses (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_assignments_course ON assignments (course_id)")

    # cases system
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_organization ON cases (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_assignment ON cases (assignment_id)")

    # case_result_links
    op.execute("CREATE INDEX IF NOT EXISTS idx_case_result_links_case ON case_result_links (case_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_case_result_links_similarity_result ON case_result_links (similarity_result_id)")

    # case_comments
    op.execute("CREATE INDEX IF NOT EXISTS idx_case_comments_case ON case_comments (case_id)")

    # api keys & audit
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_job ON webhook_events (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_job ON audit_logs (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id)")

    # users
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_organization ON users (organization_id)")


def downgrade() -> None:
    # Use IF EXISTS for safety
    op.execute("DROP INDEX IF EXISTS idx_users_organization")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_user")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_job")
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_job")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_tenant")
    op.execute("DROP INDEX IF EXISTS idx_case_comments_case")
    op.execute("DROP INDEX IF EXISTS idx_case_result_links_similarity_result")
    op.execute("DROP INDEX IF EXISTS idx_case_result_links_case")
    op.execute("DROP INDEX IF EXISTS idx_cases_assignment")
    op.execute("DROP INDEX IF EXISTS idx_cases_organization")
    op.execute("DROP INDEX IF EXISTS idx_assignments_course")
    op.execute("DROP INDEX IF EXISTS idx_courses_organization")
    op.execute("DROP INDEX IF EXISTS idx_submissions_job")