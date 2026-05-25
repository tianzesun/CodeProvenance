"""add_fpr_validation_runs_table

Revision ID: f2a3b4c5d6e7
Revises: 59c3fdf988f5
Create Date: 2026-05-24 18:58:21.000000

Adds the fpr_validation_runs table to persist Real FPR Validation runs
for history, comparison between runs, and future certification/locked baseline features.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = '59c3fdf988f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # fpr_validation_runs
    op.execute("""
        CREATE TABLE IF NOT EXISTS fpr_validation_runs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            user_id UUID REFERENCES users(id),
            name VARCHAR(255) NOT NULL,
            payload JSONB NOT NULL,
            num_submissions INTEGER,
            num_pairs INTEGER,
            mean_score NUMERIC(5, 4),
            max_score NUMERIC(5, 4),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_fpr_runs_tenant_created ON fpr_validation_runs (tenant_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_fpr_runs_user ON fpr_validation_runs (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_fpr_runs_user")
    op.execute("DROP INDEX IF EXISTS idx_fpr_runs_tenant_created")
    op.execute("DROP TABLE IF EXISTS fpr_validation_runs")
