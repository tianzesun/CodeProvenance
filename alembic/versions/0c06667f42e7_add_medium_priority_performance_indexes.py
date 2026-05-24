"""add_medium_priority_performance_indexes

Revision ID: 0c06667f42e7
Revises: 59c3fdf988f5
Create Date: 2026-05-23 14:36:12.846164

Adds medium-priority performance indexes on additional foreign keys
and time-based columns that are commonly used in queries but were
not critical enough for the first performance index migration.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c06667f42e7'
down_revision = '59c3fdf988f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # jobs
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_assignment ON jobs (assignment_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at)")

    # similarity_results
    op.execute("CREATE INDEX IF NOT EXISTS idx_similarity_results_created_at ON similarity_results (created_at)")

    # submissions
    op.execute("CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON submissions (created_at)")

    # cases
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_created_by ON cases (created_by_id)")

    # case_comments
    op.execute("CREATE INDEX IF NOT EXISTS idx_case_comments_user ON case_comments (user_id)")

    # webhook_events
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events (status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_next_attempt ON webhook_events (next_attempt_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_next_attempt")
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_status")
    op.execute("DROP INDEX IF EXISTS idx_case_comments_user")
    op.execute("DROP INDEX IF EXISTS idx_cases_created_by")
    op.execute("DROP INDEX IF EXISTS idx_submissions_created_at")
    op.execute("DROP INDEX IF EXISTS idx_similarity_results_created_at")
    op.execute("DROP INDEX IF EXISTS idx_jobs_created_at")
    op.execute("DROP INDEX IF EXISTS idx_jobs_assignment")
