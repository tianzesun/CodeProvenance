"""add viva_outcomes table

Revision ID: e2f4a6b8c0d1
Revises: d9e8f7a6b5c4
Create Date: 2026-08-22 15:30:00.000000

Records the outcome of a viva (authorship interview) per student submission
so the dossier's case loop can be closed: the professor runs the viva using
the generated questions, then records what was concluded. One row per
(job, submission) — re-recording upserts. Made idempotent so it can run
safely against either a fresh or partially migrated schema.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e2f4a6b8c0d1"
down_revision = "d9e8f7a6b5c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS viva_outcomes (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            job_id VARCHAR(36) NOT NULL
                REFERENCES jobs(id) ON DELETE CASCADE,
            submission_name VARCHAR(500) NOT NULL,
            outcome VARCHAR(50) NOT NULL,
            notes TEXT,
            conducted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_viva_outcomes_job_submission
                UNIQUE (job_id, submission_name)
        )
    """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_viva_outcomes_outcome
        ON viva_outcomes (outcome)
    """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_viva_outcomes_outcome")
    op.execute("DROP TABLE IF EXISTS viva_outcomes")
