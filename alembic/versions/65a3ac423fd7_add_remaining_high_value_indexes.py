"""add_remaining_high_value_indexes

Revision ID: 65a3ac423fd7
Revises: b14dc0427c69
Create Date: 2026-05-23 22:45:52.928063

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65a3ac423fd7'
down_revision = 'b14dc0427c69'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Standalone status index on jobs (very frequently filtered by status)
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)")

    # Composite for time-based status filtering (e.g. "recent failed jobs")
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at ON jobs (status, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_status_created_at")
    op.execute("DROP INDEX IF EXISTS idx_jobs_status")
