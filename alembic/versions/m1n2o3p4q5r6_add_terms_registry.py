"""add_terms_registry

Revision ID: m1n2o3p4q5r6
Revises: k5l6m7n8o9p0
Create Date: 2026-09-26 00:00:00.000000

Introduces an organization-scoped academic ``terms`` registry so a new term can
be created up front and then assigned to courses:

* creates table ``terms`` (unique per organization on name + year)
* adds nullable ``courses.term_id`` FK back to it

Existing ``courses.term`` / ``courses.year`` text columns are intentionally kept
and backfilled: they are read by historical cross-term matching and reporting, so
the registry is additive rather than a replacement. Courses whose term text did
not match a registrable (name, year) pair keep ``term_id`` NULL and continue to
work exactly as before.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "m1n2o3p4q5r6"
down_revision = "k5l6m7n8o9p0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the terms registry and link existing courses to it."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS terms (
            id UUID NOT NULL DEFAULT uuid_generate_v4() PRIMARY KEY,
            organization_id UUID NOT NULL,
            name VARCHAR(50) NOT NULL,
            year INTEGER NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            CONSTRAINT terms_organization_id_fkey
                FOREIGN KEY (organization_id) REFERENCES organizations (id),
            CONSTRAINT uq_terms_org_name_year
                UNIQUE (organization_id, name, year)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_terms_organization ON terms (organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_terms_org_year ON terms (organization_id, year)"
    )
    op.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS term_id UUID")
    op.execute(
        """
        ALTER TABLE courses
        ADD CONSTRAINT courses_term_id_fkey
            FOREIGN KEY (term_id) REFERENCES terms (id)
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_courses_term ON courses (term_id)")

    # Backfill: create a registry row for every distinct course term/year pair,
    # then point the course at it. Restricted to known season names so odd
    # free-text values (e.g. "Fall 2024 - section B") are left untouched.
    op.execute(
        """
        INSERT INTO terms (organization_id, name, year)
        SELECT DISTINCT organization_id, initcap(btrim(term)), year
        FROM courses
        WHERE term IS NOT NULL
          AND btrim(term) <> ''
          AND year IS NOT NULL
          AND lower(btrim(term)) IN ('winter', 'spring', 'summer', 'fall', 'autumn')
        ON CONFLICT (organization_id, name, year) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE courses AS c
        SET term_id = t.id
        FROM terms AS t
        WHERE t.organization_id = c.organization_id
          AND t.year = c.year
          AND lower(t.name) = lower(btrim(c.term))
          AND c.term IS NOT NULL
          AND btrim(c.term) <> ''
          AND c.year IS NOT NULL
        """
    )


def downgrade() -> None:
    """Remove the terms registry and the course link (rollback)."""
    # The mirrored courses.term / courses.year text columns are untouched, so no
    # course loses its term on rollback.
    op.execute("ALTER TABLE courses DROP CONSTRAINT IF EXISTS courses_term_id_fkey")
    op.execute("DROP INDEX IF EXISTS idx_courses_term")
    op.execute("ALTER TABLE courses DROP COLUMN IF EXISTS term_id")
    op.execute("DROP TABLE IF EXISTS terms")
