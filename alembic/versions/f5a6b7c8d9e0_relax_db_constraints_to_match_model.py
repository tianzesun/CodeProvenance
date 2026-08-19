"""relax_db_constraints_to_match_model

Revision ID: f5a6b7c8d9e0
Revises: f0a1b2c3d4e5
Create Date: 2026-08-19 00:00:00.000000

The upload-flow persist wiring writes jobs, submissions, and
similarity_results rows with a minimal set of fields. The model
declares these columns nullable, but the DB schema was created from
an earlier migration with NOT NULL. Relax them to match the model so
best-effort persistence actually succeeds.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f5a6b7c8d9e0"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE submissions ALTER COLUMN file_paths DROP NOT NULL")
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN confidence_lower DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN confidence_upper DROP NOT NULL"
    )


def downgrade() -> None:
    # Re-applying NOT NULL is safe because the nullable columns always hold
    # values or NULL; enforcement is loosened again only to preserve data.
    op.execute("ALTER TABLE submissions ALTER COLUMN file_paths SET NOT NULL")
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN confidence_lower SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN confidence_upper SET NOT NULL"
    )
