"""fix_schema_drift

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-09-14 22:00:00.000000

Repairs three gaps between the ORM models and the live database:

1. Creates the ``students`` table (referenced by submissions.student_id FK).
   The ORM model has existed for a long time but was never migrated.

2. Adds the ``student_id`` column to ``submissions``.  All existing rows
   receive NULL (the column is nullable — no back-fill required).

3. Creates ``pair_reviews`` and ``band_thresholds`` (previously added in
   revision i3j4k5l6m7n8 but never applied because the DB was still at
   h2i3j4k5l6m7 when that migration was written).

Rollback removes the two new tables and the student_id column.
The ``students`` table is NOT dropped on rollback because it may have been
independently created by other means; its creation is guarded with
``IF NOT EXISTS``.
"""

from alembic import op

revision = "j4k5l6m7n8o9"
down_revision = "i3j4k5l6m7n8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. students table
    #    Must exist before submissions.student_id FK can be added.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            organization_id UUID NOT NULL REFERENCES organizations(id),
            email           VARCHAR(255) NOT NULL,
            full_name       VARCHAR(255) NOT NULL,
            student_number  VARCHAR(50),
            settings        JSONB NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_students_organization "
        "ON students (organization_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_students_email "
        "ON students (email);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_students_student_number "
        "ON students (student_number) WHERE student_number IS NOT NULL;"
    )

    # ------------------------------------------------------------------
    # 2. submissions.student_id
    #    Nullable FK — all existing rows keep NULL.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE submissions
        ADD COLUMN IF NOT EXISTS student_id UUID
            REFERENCES students(id) ON DELETE SET NULL;
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_submissions_student "
        "ON submissions (student_id) WHERE student_id IS NOT NULL;"
    )

    # ------------------------------------------------------------------
    # 3. pair_reviews  (review disposition history, append-only)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS pair_reviews (
            id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            job_id           VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            submission_a     VARCHAR(255) NOT NULL,
            submission_b     VARCHAR(255) NOT NULL,
            reviewer_id      UUID NOT NULL REFERENCES users(id),
            reviewed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            band             VARCHAR(16) NOT NULL
                                 CHECK (band IN ('low', 'review', 'high')),
            disposition      VARCHAR(32) NOT NULL
                                 CHECK (disposition IN (
                                     'no_action', 'note_on_file', 'conversation',
                                     'step_up_verification', 'formal_escalation'
                                 )),
            rationale        TEXT,
            ai_flag          BOOLEAN NOT NULL DEFAULT FALSE,
            corroborated     BOOLEAN NOT NULL DEFAULT FALSE,
            similarity_score NUMERIC(5, 4),
            appeal_status    VARCHAR(16)
                                 CHECK (appeal_status IS NULL OR appeal_status IN (
                                     'submitted', 'under_review', 'upheld', 'overturned'
                                 )),
            appeal_submitted_at  TIMESTAMPTZ,
            appeal_outcome_at    TIMESTAMPTZ,
            appeal_notes         TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pair_reviews_job "
        "ON pair_reviews (job_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pair_reviews_job_band "
        "ON pair_reviews (job_id, band);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pair_reviews_job_pair "
        "ON pair_reviews (job_id, submission_a, submission_b);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pair_reviews_reviewer "
        "ON pair_reviews (reviewer_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pair_reviews_reviewed_at "
        "ON pair_reviews (reviewed_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pair_reviews_disposition "
        "ON pair_reviews (disposition);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pair_reviews_appeal_status "
        "ON pair_reviews (appeal_status) WHERE appeal_status IS NOT NULL;"
    )

    # ------------------------------------------------------------------
    # 4. band_thresholds  (per-mode review band configuration)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS band_thresholds (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            assignment_mode VARCHAR(64) NOT NULL UNIQUE,
            review_min      NUMERIC(4, 3) NOT NULL,
            high_min        NUMERIC(4, 3) NOT NULL,
            ai_elevated_min NUMERIC(4, 3) NOT NULL DEFAULT 0.650,
            web_match_min   NUMERIC(4, 3) NOT NULL DEFAULT 0.700,
            engine_agree_count  INTEGER NOT NULL DEFAULT 2,
            engine_agree_min    NUMERIC(4, 3) NOT NULL DEFAULT 0.500,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_band_thresholds_review_lt_high
                CHECK (review_min < high_min),
            CONSTRAINT ck_band_thresholds_review_range
                CHECK (review_min >= 0 AND review_min <= 1),
            CONSTRAINT ck_band_thresholds_high_range
                CHECK (high_min >= 0 AND high_min <= 1)
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_band_thresholds_mode "
        "ON band_thresholds (assignment_mode);"
    )
    # Seed default thresholds
    op.execute("""
        INSERT INTO band_thresholds
            (assignment_mode, review_min, high_min, ai_elevated_min)
        VALUES
            ('introductory', 0.450, 0.700, 0.650),
            ('algorithms',   0.350, 0.650, 0.650),
            ('projects',     0.250, 0.550, 0.650),
            ('capstone',     0.200, 0.500, 0.650),
            ('default',      0.350, 0.650, 0.650)
        ON CONFLICT (assignment_mode) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS band_thresholds CASCADE;")
    op.execute("DROP TABLE IF EXISTS pair_reviews CASCADE;")
    op.execute(
        "DROP INDEX IF EXISTS idx_submissions_student;"
    )
    op.execute("""
        ALTER TABLE submissions
        DROP COLUMN IF EXISTS student_id;
    """)
    # NOTE: students table is intentionally NOT dropped on rollback.
    # Dropping it would cascade-delete any student rows created after
    # this migration ran.  Re-run this migration to recreate it if needed.
