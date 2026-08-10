"""add_ai_detection_results

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-08-10 12:00:00.000000

Adds the ai_detection_results table to persist per-submission AI-generated
code likelihood scores, separate from similarity_results. Schema mirrors the
``AIDetectionResult`` model in src/backend/models/database.py, with a downgrade
that drops the table and its indexes.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_detection_results (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            job_id UUID NOT NULL,
            submission_name VARCHAR(500) NOT NULL,
            language VARCHAR(50),
            ai_probability NUMERIC(5, 4),
            confidence NUMERIC(3, 2),
            method VARCHAR(50),
            model_name VARCHAR(500),
            status VARCHAR(50),
            indicators JSONB,
            signals JSONB,
            signal_labels JSONB,
            flagged_lines JSONB,
            flagged_regions JSONB,
            classifier_details JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_detection_results_job "
        "ON ai_detection_results (job_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_detection_results_job_probability "
        "ON ai_detection_results (job_id, ai_probability)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_detection_results_ai_probability "
        "ON ai_detection_results (ai_probability)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_detection_results_language "
        "ON ai_detection_results (language)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_detection_results_created_at "
        "ON ai_detection_results (created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ai_detection_results_created_at")
    op.execute("DROP INDEX IF EXISTS idx_ai_detection_results_language")
    op.execute("DROP INDEX IF EXISTS idx_ai_detection_results_ai_probability")
    op.execute("DROP INDEX IF EXISTS idx_ai_detection_results_job_probability")
    op.execute("DROP INDEX IF EXISTS idx_ai_detection_results_job")
    op.execute("DROP TABLE IF EXISTS ai_detection_results")
