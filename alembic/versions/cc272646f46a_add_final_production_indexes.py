"""add_final_production_indexes

Revision ID: cc272646f46a
Revises: 65a3ac423fd7
Create Date: 2026-05-23 22:55:04.127967

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cc272646f46a'
down_revision = '65a3ac423fd7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Audit logs - action is very commonly filtered
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action)")

    # Similarity results - excellent for time-based review dashboards ("recent unreviewed")
    op.execute("CREATE INDEX IF NOT EXISTS idx_similarity_results_review_created_at ON similarity_results (review_status, created_at)")

    # Webhook events - critical for efficient retry scheduling
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_status_next_attempt ON webhook_events (status, next_attempt_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_webhook_events_status_next_attempt")
    op.execute("DROP INDEX IF EXISTS idx_similarity_results_review_created_at")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_action")
