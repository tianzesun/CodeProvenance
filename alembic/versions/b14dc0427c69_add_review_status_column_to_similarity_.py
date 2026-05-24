"""add_review_status_column_to_similarity_results

Revision ID: b14dc0427c69
Revises: 0d621dcbb485
Create Date: 2026-05-23 22:06:45.045961

Adds the `review_status` column (if missing) and its index.
Made idempotent so it can run safely even if the column was already
added by the previous composite migration.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b14dc0427c69'
down_revision = '0d621dcbb485'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column if it doesn't exist yet
    op.execute("""
        ALTER TABLE similarity_results 
        ADD COLUMN IF NOT EXISTS review_status VARCHAR(50)
    """)

    # Create the index if it doesn't exist
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_similarity_results_review_status 
        ON similarity_results (review_status)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_similarity_results_review_status")
    op.execute("ALTER TABLE similarity_results DROP COLUMN IF EXISTS review_status")
