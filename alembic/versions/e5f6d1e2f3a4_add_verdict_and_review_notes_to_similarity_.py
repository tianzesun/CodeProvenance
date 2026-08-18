"""add verdict and review_notes columns to similarity_results

Revision ID: e5f6d1e2f3a4
Revises: c0d1e2f3a4b5
Create Date: 2026-08-18 19:30:00.000000

Adds the `verdict` and `review_notes` columns (and the verdict index) that
the SimilarityResult model has expected since commit 63880cd3 but which no
migration ever added. Made idempotent so it can run safely against either a
fresh or partially migrated schema.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6d1e2f3a4"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns if they don't exist yet
    op.execute("""
        ALTER TABLE similarity_results
        ADD COLUMN IF NOT EXISTS verdict VARCHAR(20)
    """)
    op.execute("""
        ALTER TABLE similarity_results
        ADD COLUMN IF NOT EXISTS review_notes TEXT
    """)

    # Create the index if it doesn't exist
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_similarity_results_verdict
        ON similarity_results (verdict)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_similarity_results_verdict")
    op.execute("ALTER TABLE similarity_results DROP COLUMN IF EXISTS review_notes")
    op.execute("ALTER TABLE similarity_results DROP COLUMN IF EXISTS verdict")