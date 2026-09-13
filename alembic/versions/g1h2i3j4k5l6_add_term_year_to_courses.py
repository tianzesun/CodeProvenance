"""add_term_year_to_courses

Revision ID: g1h2i3j4k5l6
Revises: f9a8b7c6d5e4
Create Date: 2026-09-12 15:45:00.000000

Adds term and year columns to courses table for academic term support.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "g1h2i3j4k5l6"
down_revision = "f9a8b7c6d5e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add term and year columns to courses."""
    op.execute(
        """
        ALTER TABLE courses
        ADD COLUMN IF NOT EXISTS term VARCHAR(50),
        ADD COLUMN IF NOT EXISTS year INTEGER
        """
    )


def downgrade() -> None:
    """Drop term and year columns from courses."""
    op.execute(
        """
        ALTER TABLE courses
        DROP COLUMN IF EXISTS year,
        DROP COLUMN IF EXISTS term
        """
    )
