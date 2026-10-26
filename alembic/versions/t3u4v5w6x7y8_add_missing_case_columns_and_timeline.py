"""add case columns and timeline_events that no migration created

Revision ID: t3u4v5w6x7y8
Revises: s2t3u4v5w6x7
Create Date: 2026-10-25 00:00:00.000000

The models have cases.priority, cases.investigator_id, cases.closed_at and
the timeline_events table, but no migration ever created them: live databases
got them from Base.metadata.create_all() or by hand. A fresh install built
with ``alembic upgrade head`` therefore failed on the first case insert.
scripts/check_schema_drift.py found these in CI.

Everything is IF NOT EXISTS, so databases that already have them are
unchanged. Downgrade is a no-op: on those databases the columns and table
predate this revision and hold real case history, so dropping them would
destroy data.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "t3u4v5w6x7y8"
down_revision = "s2t3u4v5w6x7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'MEDIUM',
            ADD COLUMN IF NOT EXISTS investigator_id UUID REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS timeline_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
            job_id VARCHAR(36) REFERENCES jobs(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id),
            event_type VARCHAR(100) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """
    )
    for name, columns in (
        ("idx_timeline_job", "job_id"),
        ("idx_timeline_user", "user_id"),
        ("idx_timeline_created_at", "created_at"),
        ("idx_timeline_case_created", "case_id, created_at"),
    ):
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON timeline_events ({columns})")


def downgrade() -> None:
    # Intentionally empty; see the module docstring.
    pass
