"""add_assignment_versions_table

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-09-26 00:00:00.000000

Creates the ``assignment_versions`` table.

The ``AssignmentVersion`` ORM model has existed for a long time but was never
migrated, while ``Assignment.versions`` declares a relationship to it. That made
every ORM load and every assignment delete fail at runtime with::

    UndefinedTable: relation "assignment_versions" does not exist

because SQLAlchemy emits the join/cascade query even when the collection is
never accessed. This revision closes that drift.

Both foreign keys cascade on delete, matching the ``ondelete="CASCADE"`` already
declared on the model, so deleting an assignment or a course removes its
versions.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "n2o3p4q5r6s7"
down_revision = "m1n2o3p4q5r6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the assignment_versions table."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS assignment_versions (
            id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            assignment_id  UUID NOT NULL
                REFERENCES assignments(id) ON DELETE CASCADE,
            course_id      UUID NOT NULL
                REFERENCES courses(id) ON DELETE CASCADE,
            version        INTEGER NOT NULL DEFAULT 1,
            name           VARCHAR(255) NOT NULL,
            description    TEXT,
            starter_files  JSONB,
            settings       JSONB NOT NULL DEFAULT '{}',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT uq_assignment_versions_assignment_version
                UNIQUE (assignment_id, version)
        );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignment_versions_assignment "
        "ON assignment_versions (assignment_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignment_versions_course "
        "ON assignment_versions (course_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignment_versions_active "
        "ON assignment_versions (assignment_id) WHERE is_active IS TRUE;"
    )


def downgrade() -> None:
    """Drop the assignment_versions table (rollback).

    Safe to run unconditionally: the table holds no data that cannot be
    recreated, and every row is derived from its parent assignment.
    """
    op.execute("DROP TABLE IF EXISTS assignment_versions CASCADE;")
