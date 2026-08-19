"""widen_similarity_submission_ids_to_varchar

Revision ID: f7e8d9c0b1a2
Revises: f5a6b7c8d9e0
Create Date: 2026-08-19 00:00:00.000000

The app round-trips filenames in similarity_results.submission_a_id/b_id
(see _load_job_from_db and the per-pair review query in server.py), but
the DB columns were UUID with foreign keys to submissions. The model never
declared those FKs. Widen the columns to VARCHAR(255) and drop the stale
foreign keys so best-effort persistence and review round-trips work.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f7e8d9c0b1a2"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the FKs and the duplicate-pair check first so the type change is allowed.
    op.execute(
        "ALTER TABLE similarity_results DROP CONSTRAINT IF EXISTS similarity_results_submission_a_id_fkey"
    )
    op.execute(
        "ALTER TABLE similarity_results DROP CONSTRAINT IF EXISTS similarity_results_submission_b_id_fkey"
    )
    op.execute(
        "ALTER TABLE similarity_results DROP CONSTRAINT IF EXISTS ck_no_duplicate_pairs"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_a_id TYPE VARCHAR(255)"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_b_id TYPE VARCHAR(255)"
    )
    op.execute(
        "ALTER TABLE similarity_results ADD CONSTRAINT ck_no_duplicate_pairs CHECK (submission_a_id < submission_b_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_a_id DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_b_id DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE similarity_results DROP CONSTRAINT IF EXISTS ck_no_duplicate_pairs"
    )
    op.execute(
        "DELETE FROM similarity_results WHERE submission_a_id NOT SIMILAR TO '[0-9a-fA-F-]{36}'"
    )
    op.execute(
        "DELETE FROM similarity_results WHERE submission_b_id NOT SIMILAR TO '[0-9a-fA-F-]{36}'"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_a_id TYPE UUID USING submission_a_id::uuid"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_b_id TYPE UUID USING submission_b_id::uuid"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_a_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE similarity_results ALTER COLUMN submission_b_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE similarity_results ADD CONSTRAINT ck_no_duplicate_pairs CHECK (submission_a_id < submission_b_id)"
    )
    op.execute(
        "ALTER TABLE similarity_results ADD CONSTRAINT similarity_results_submission_a_id_fkey FOREIGN KEY (submission_a_id) REFERENCES submissions(id)"
    )
    op.execute(
        "ALTER TABLE similarity_results ADD CONSTRAINT similarity_results_submission_b_id_fkey FOREIGN KEY (submission_b_id) REFERENCES submissions(id)"
    )
