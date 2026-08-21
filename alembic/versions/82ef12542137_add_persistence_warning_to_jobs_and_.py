"""add persistence_warning to jobs and retention_days to tenants

Revision ID: 82ef12542137
Revises: f7e8d9c0b1a2
Create Date: 2026-08-21 11:31:31.154189

"""

from alembic import op
import sqlalchemy as sa

revision = "82ef12542137"
down_revision = "f7e8d9c0b1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("persistence_warning", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("retention_days", sa.Integer(), nullable=True, server_default="365"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "retention_days")
    op.drop_column("jobs", "persistence_warning")
