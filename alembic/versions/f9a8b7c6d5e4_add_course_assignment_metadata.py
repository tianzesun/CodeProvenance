"""add_course_assignment_metadata

Revision ID: f9a8b7c6d5e4
Revises: e2f4a6b8c0d1
Create Date: 2026-09-12 00:00:00.000000

Adds analytics metadata to courses and assignments for the multi-course
academic-integrity platform:

* courses.department, courses.description
* assignments.assignment_type, description, max_score, team_mode, open_book,
  time_limited, allowed_resources, detection_config
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f9a8b7c6d5e4"
down_revision = "e2f4a6b8c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add course and assignment analytics metadata columns."""
    op.execute(
        """
        ALTER TABLE courses
        ADD COLUMN IF NOT EXISTS department VARCHAR(100),
        ADD COLUMN IF NOT EXISTS description TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE assignments
        ADD COLUMN IF NOT EXISTS assignment_type VARCHAR(40) NOT NULL
            DEFAULT 'programming',
        ADD COLUMN IF NOT EXISTS description TEXT,
        ADD COLUMN IF NOT EXISTS max_score FLOAT,
        ADD COLUMN IF NOT EXISTS team_mode VARCHAR(20) NOT NULL
            DEFAULT 'individual',
        ADD COLUMN IF NOT EXISTS open_book BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS time_limited BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS allowed_resources JSONB NOT NULL DEFAULT '[]',
        ADD COLUMN IF NOT EXISTS detection_config JSONB NOT NULL DEFAULT '{}'
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignments_type "
        "ON assignments (assignment_type)"
    )


def downgrade() -> None:
    """Drop the analytics metadata columns (rollback)."""
    op.execute("DROP INDEX IF EXISTS idx_assignments_type")
    op.execute(
        """
        ALTER TABLE assignments
        DROP COLUMN IF EXISTS detection_config,
        DROP COLUMN IF EXISTS allowed_resources,
        DROP COLUMN IF EXISTS time_limited,
        DROP COLUMN IF EXISTS open_book,
        DROP COLUMN IF EXISTS team_mode,
        DROP COLUMN IF EXISTS max_score,
        DROP COLUMN IF EXISTS description,
        DROP COLUMN IF EXISTS assignment_type
        """
    )
    op.execute(
        """
        ALTER TABLE courses
        DROP COLUMN IF EXISTS description,
        DROP COLUMN IF EXISTS department
        """
    )
