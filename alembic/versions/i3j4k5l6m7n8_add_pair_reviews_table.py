"""add_pair_reviews_table

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-09-14 20:00:00.000000

Creates the pair_reviews table that stores faculty review decisions (dispositions)
for flagged submission pairs.  Rows are append-only — history is preserved by
inserting a new row rather than updating an existing one.  The latest row for a
(job_id, submission_a, submission_b) triplet represents the current state.

Also creates the band_thresholds table, which stores per-assignment-mode numeric
thresholds for Low / Review / High bands.  Thresholds are DB-configured so they
can be adjusted without a code deploy.
"""

from alembic import op

# revision identifiers
revision = "i3j4k5l6m7n8"
down_revision = "h2i3j4k5l6m7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # pair_reviews  — faculty disposition records (append-only)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS pair_reviews (
            id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

            -- which job and which pair
            job_id           VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            submission_a     VARCHAR(255) NOT NULL,
            submission_b     VARCHAR(255) NOT NULL,

            -- who reviewed and when
            reviewer_id      UUID NOT NULL REFERENCES users(id),
            reviewed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- computed band at review time (low | review | high)
            band             VARCHAR(16) NOT NULL
                                 CHECK (band IN ('low', 'review', 'high')),

            -- faculty decision
            disposition      VARCHAR(32) NOT NULL
                                 CHECK (disposition IN (
                                     'no_action',
                                     'note_on_file',
                                     'conversation',
                                     'step_up_verification',
                                     'formal_escalation'
                                 )),

            -- optional rationale (max ~500 chars enforced in application layer)
            rationale        TEXT,

            -- AI corroboration state at review time
            ai_flag          BOOLEAN NOT NULL DEFAULT FALSE,
            corroborated     BOOLEAN NOT NULL DEFAULT FALSE,

            -- similarity score recorded at review time (for analytics)
            similarity_score NUMERIC(5, 4),

            -- future-proofing: appeal fields (nullable — no migration needed later)
            appeal_status    VARCHAR(16)
                                 CHECK (appeal_status IS NULL OR appeal_status IN (
                                     'submitted',
                                     'under_review',
                                     'upheld',
                                     'overturned'
                                 )),
            appeal_submitted_at  TIMESTAMPTZ,
            appeal_outcome_at    TIMESTAMPTZ,
            appeal_notes         TEXT,

            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # Indexes optimised for the common access patterns:
    #   - faculty opens a job → filter by job_id, order by band/score
    #   - analytics → group by job_id + band + disposition
    #   - admin audit → filter by reviewer_id
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
    # band_thresholds  — per-assignment-mode Low/Review/High thresholds
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS band_thresholds (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            assignment_mode VARCHAR(64) NOT NULL UNIQUE,

            -- lower edges of Review and High bands (0.0–1.0)
            review_min      NUMERIC(4, 3) NOT NULL,
            high_min        NUMERIC(4, 3) NOT NULL,

            -- AI corroboration: minimum score to consider AI flag elevated
            ai_elevated_min NUMERIC(4, 3) NOT NULL DEFAULT 0.650,

            -- minimum score for a web-match snippet to count as corroboration
            web_match_min   NUMERIC(4, 3) NOT NULL DEFAULT 0.700,

            -- minimum number of engines that must individually score >= engine_agree_min
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

    # Seed default thresholds for the four canonical assignment modes.
    # These match the design spec values; admins can UPDATE rows directly.
    op.execute("""
        INSERT INTO band_thresholds
            (assignment_mode, review_min, high_min, ai_elevated_min)
        VALUES
            ('introductory',  0.450, 0.700, 0.650),
            ('algorithms',    0.350, 0.650, 0.650),
            ('projects',      0.250, 0.550, 0.650),
            ('capstone',      0.200, 0.500, 0.650),
            ('default',       0.350, 0.650, 0.650)
        ON CONFLICT (assignment_mode) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pair_reviews CASCADE;")
    op.execute("DROP TABLE IF EXISTS band_thresholds CASCADE;")
