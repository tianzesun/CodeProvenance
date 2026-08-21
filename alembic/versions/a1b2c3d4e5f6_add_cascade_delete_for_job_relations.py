"""add cascade delete for job-related tables

Revision ID: a1b2c3d4e5f6
Revises: 82ef12542137
Create Date: 2026-08-21 16:00:00.000000

"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "82ef12542137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_job_id_fkey")
    op.execute(
        "ALTER TABLE reports ADD CONSTRAINT reports_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_related_job_id_fkey"
    )
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT notifications_related_job_id_fkey FOREIGN KEY (related_job_id) REFERENCES jobs(id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE behavioral_sessions DROP CONSTRAINT IF EXISTS behavioral_sessions_job_id_fkey"
    )
    op.execute(
        "ALTER TABLE behavioral_sessions ADD CONSTRAINT behavioral_sessions_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE timeline_events DROP CONSTRAINT IF EXISTS timeline_events_job_id_fkey"
    )
    op.execute(
        "ALTER TABLE timeline_events ADD CONSTRAINT timeline_events_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE timeline_events DROP CONSTRAINT IF EXISTS timeline_events_job_id_fkey"
    )
    op.execute(
        "ALTER TABLE timeline_events ADD CONSTRAINT timeline_events_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id)"
    )
    op.execute(
        "ALTER TABLE behavioral_sessions DROP CONSTRAINT IF EXISTS behavioral_sessions_job_id_fkey"
    )
    op.execute(
        "ALTER TABLE behavioral_sessions ADD CONSTRAINT behavioral_sessions_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id)"
    )
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_related_job_id_fkey"
    )
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT notifications_related_job_id_fkey FOREIGN KEY (related_job_id) REFERENCES jobs(id)"
    )
    op.execute("ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_job_id_fkey")
    op.execute(
        "ALTER TABLE reports ADD CONSTRAINT reports_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id)"
    )
