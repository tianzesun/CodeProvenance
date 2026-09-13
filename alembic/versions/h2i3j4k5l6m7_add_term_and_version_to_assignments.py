"""add_term_and_version_to_assignments

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-09-12 16:00:00.000000

Adds term and version columns to assignments table to match the Assignment model.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "h2i3j4k5l6m7"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add term and version columns to assignments."""
    op.execute(
        """
        ALTER TABLE assignments
        ADD COLUMN IF NOT EXISTS term VARCHAR(50),
        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1
        """
    )


def downgrade() -> None:
    """Drop term and version columns from assignments."""
    op.execute(
        """
        ALTER TABLE assignments
        DROP COLUMN IF EXISTS version,
        DROP COLUMN IF EXISTS term
        """
    )
