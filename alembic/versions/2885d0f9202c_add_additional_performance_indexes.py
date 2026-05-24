"""add_additional_performance_indexes

Revision ID: 2885d0f9202c
Revises: 0c06667f42e7
Create Date: 2026-05-23 14:43:37.773067

Adds further useful indexes that improve common query patterns
(audit log time ranges, case status filtering, and submission-based
lookups in similarity results).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2885d0f9202c'
down_revision = '0c06667f42e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # audit logs - time-based queries are very common
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at)")

    # cases - status and time filtering in review dashboards
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases (status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases (created_at)")

    # similarity_results - lookups by individual submissions
    op.execute("CREATE INDEX IF NOT EXISTS idx_similarity_results_submission_a ON similarity_results (submission_a_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_similarity_results_submission_b ON similarity_results (submission_b_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_similarity_results_submission_b")
    op.execute("DROP INDEX IF EXISTS idx_similarity_results_submission_a")
    op.execute("DROP INDEX IF EXISTS idx_cases_created_at")
    op.execute("DROP INDEX IF EXISTS idx_cases_status")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_created_at")

