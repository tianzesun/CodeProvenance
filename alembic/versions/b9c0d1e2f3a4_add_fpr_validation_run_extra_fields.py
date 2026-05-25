"""add_fpr_validation_run_extra_fields

Revision ID: b9c0d1e2f3a4
Revises: a7b8c9d0e1f2
Create Date: 2026-05-24 19:12:00.000000

Adds additional columns to fpr_validation_runs for better decision support,
certification workflow, and user notes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9c0d1e2f3a4'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for decision support and certification
    op.execute("""
        ALTER TABLE fpr_validation_runs
        ADD COLUMN IF NOT EXISTS recommended_threshold NUMERIC(5, 2),
        ADD COLUMN IF NOT EXISTS fpr_at_recommended_threshold NUMERIC(6, 4),
        ADD COLUMN IF NOT EXISTS notes TEXT,
        ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'completed',
        ADD COLUMN IF NOT EXISTS is_certified BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS certified_by_user_id UUID REFERENCES users(id),
        ADD COLUMN IF NOT EXISTS certified_at TIMESTAMPTZ
    """)

    # Add useful indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_fpr_runs_tenant_status ON fpr_validation_runs (tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_fpr_runs_certified ON fpr_validation_runs (is_certified)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_fpr_runs_certified")
    op.execute("DROP INDEX IF EXISTS idx_fpr_runs_tenant_status")

    op.execute("""
        ALTER TABLE fpr_validation_runs
        DROP COLUMN IF EXISTS certified_at,
        DROP COLUMN IF EXISTS certified_by_user_id,
        DROP COLUMN IF EXISTS is_certified,
        DROP COLUMN IF EXISTS status,
        DROP COLUMN IF EXISTS notes,
        DROP COLUMN IF EXISTS fpr_at_recommended_threshold,
        DROP COLUMN IF EXISTS recommended_threshold
    """)
