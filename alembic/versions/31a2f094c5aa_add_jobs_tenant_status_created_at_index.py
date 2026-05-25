"""add_jobs_tenant_status_created_at_index

Revision ID: 31a2f094c5aa
Revises: cc272646f46a
Create Date: 2026-05-23 23:04:19.029338

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '31a2f094c5aa'
down_revision = 'cc272646f46a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Highly useful 3-column index for common tenant + status + recency queries
    # e.g. "show me the 50 most recent failed/completed jobs for my tenant"
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status_created_at "
        "ON jobs (tenant_id, status, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_tenant_status_created_at")
