"""add_term_date_window

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-09-28 00:00:00.000000

Adds an optional calendar window to the ``terms`` registry created by
``m1n2o3p4q5r6``:

* ``terms.start_date`` / ``terms.end_date`` (nullable ``DATE``)

Both columns are optional metadata for planning; no existing behavior depends
on them, so the migration is purely additive and rows keep ``NULL``. A CHECK
constraint keeps the window ordered when both ends are supplied.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "o3p4q5r6s7t8"
down_revision = "n2o3p4q5r6s7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the optional term start/end date window."""
    op.execute("ALTER TABLE terms ADD COLUMN IF NOT EXISTS start_date DATE")
    op.execute("ALTER TABLE terms ADD COLUMN IF NOT EXISTS end_date DATE")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'terms_valid_date_window'
            ) THEN
                ALTER TABLE terms
                ADD CONSTRAINT terms_valid_date_window
                    CHECK (start_date IS NULL OR end_date IS NULL OR start_date <= end_date);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Drop the term date window (rollback)."""
    op.execute("ALTER TABLE terms DROP CONSTRAINT IF EXISTS terms_valid_date_window")
    op.execute("ALTER TABLE terms DROP COLUMN IF EXISTS end_date")
    op.execute("ALTER TABLE terms DROP COLUMN IF EXISTS start_date")
