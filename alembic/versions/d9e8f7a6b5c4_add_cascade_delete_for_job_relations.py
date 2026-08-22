"""add cascade delete for job-related tables

Revision ID: d9e8f7a6b5c4
Revises: 82ef12542137
Create Date: 2026-08-21 16:00:00.000000

Originally committed with revision id ``a1b2c3d4e5f6``, which collided with
the older ``add_organization_id_to_users`` migration — alembic cannot load a
script directory containing two revisions with the same id, so every alembic
command failed. Re-issued here under a fresh id; nothing ever chained onto
the old id. If an environment stamped ``a1b2c3d4e5f6`` while intending this
migration, update its alembic_version row to ``d9e8f7a6b5c4``.
"""

from alembic import op
from sqlalchemy import text

revision = "d9e8f7a6b5c4"
down_revision = "82ef12542137"
branch_labels = None
depends_on = None

# (table, constraint, fk column) — the job-FK each statement pair retargets.
CASCADE_TARGETS = [
    ("reports", "reports_job_id_fkey", "job_id"),
    ("notifications", "notifications_related_job_id_fkey", "related_job_id"),
    ("behavioral_sessions", "behavioral_sessions_job_id_fkey", "job_id"),
    ("timeline_events", "timeline_events_job_id_fkey", "job_id"),
]


def _existing_tables() -> set:
    """Tables currently present in the public schema.

    timeline_events is created by Base.metadata.create_all() on live
    deployments but by no migration, so a from-scratch chain must skip it
    here rather than fail with "relation ... does not exist".
    """
    rows = (
        op.get_bind()
        .execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        .fetchall()
    )
    return {row[0] for row in rows}


def _retarget(on_delete: str) -> None:
    """Swap each job FK to the given delete rule, skipping missing tables."""
    present = _existing_tables()
    for table, constraint, column in CASCADE_TARGETS:
        if table not in present:
            continue
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
        rule = f" ON DELETE {on_delete}" if on_delete else ""
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY ({column}) REFERENCES jobs(id){rule}"
        )


def upgrade() -> None:
    _retarget("CASCADE")


def downgrade() -> None:
    _retarget("")
