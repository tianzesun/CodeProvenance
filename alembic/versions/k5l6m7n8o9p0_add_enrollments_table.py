"""add enrollments table

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-09-24 00:00:00.000000

The ``Enrollment`` ORM model (student roster) was never migrated, so the
``enrollments`` table is missing from the live database.  Every query that
touches it raises ``UndefinedTable``; most visibly ``GET /api/courses``,
whose broad ``except`` swallows the error and returns an empty course list
— which is why the Plagiarism Checker course dropdown was always empty.

Creation is guarded with ``IF NOT EXISTS`` so it is safe on databases where
the table was created by other means.  Rollback drops the table it created.
"""

from alembic import op

revision = "k5l6m7n8o9p0"
down_revision = "j4k5l6m7n8o9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the ``enrollments`` table and its indexes."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS enrollments (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            course_id   UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            student_id  UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            role        VARCHAR(20) DEFAULT 'student',
            CONSTRAINT uq_enrollment UNIQUE (course_id, student_id)
        );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments (course_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments (student_id);"
    )


def downgrade() -> None:
    """Drop the ``enrollments`` table created by this migration."""
    op.execute("DROP TABLE IF EXISTS enrollments CASCADE;")
