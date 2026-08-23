"""add persistence_warning to jobs and retention_days to tenants

Revision ID: 82ef12542137
Revises: f7e8d9c0b1a2
Create Date: 2026-08-21 11:31:31.154189

Made idempotent (ADD COLUMN IF NOT EXISTS / DROP COLUMN IF EXISTS): the app's
create_all() had already added these columns to live databases while this
migration could not run — alembic was broken by the duplicate revision id —
so applying the chain to a drifted database must not fail on existing
columns (the same pattern as e5f6d1e2f3a4).
"""

from alembic import op

revision = "82ef12542137"
down_revision = "f7e8d9c0b1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS persistence_warning TEXT"
    )
    op.execute(
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS retention_days INTEGER "
        "DEFAULT 365"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS retention_days")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS persistence_warning")
