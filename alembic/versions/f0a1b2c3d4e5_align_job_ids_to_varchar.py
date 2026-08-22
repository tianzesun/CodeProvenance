"""align_job_ids_to_varchar

Revision ID: f0a1b2c3d4e5
Revises: e5f6d1e2f3a4
Create Date: 2026-08-19 00:00:00.000000

Upload-flow job IDs are 8-char hex strings (str(uuid.uuid4())[:8]),
but the jobs.id and job_id FK columns were UUID. Every upload-side
DB insert failed with "invalid input syntax for type uuid" and the
error was swallowed, so jobs/submissions/similarity rows never
persisted. This migration widens these columns to VARCHAR(36).

Tables that no migration creates (webhook_events, audit_logs,
timeline_events — they appear via Base.metadata.create_all() on live
deployments) are skipped when absent, so a from-scratch alembic chain
no longer dies here with "relation ... does not exist".
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "f0a1b2c3d4e5"
down_revision = "e5f6d1e2f3a4"
branch_labels = None
depends_on = None

FOREIGN_KEYS = [
    ("submissions", "submissions_job_id_fkey", "job_id"),
    ("similarity_results", "similarity_results_job_id_fkey", "job_id"),
    ("ai_detection_results", "ai_detection_results_job_id_fkey", "job_id"),
    ("webhook_events", "webhook_events_job_id_fkey", "job_id"),
    ("audit_logs", "audit_logs_job_id_fkey", "job_id"),
    ("reports", "reports_job_id_fkey", "job_id"),
    ("notifications", "notifications_related_job_id_fkey", "related_job_id"),
    ("behavioral_sessions", "behavioral_sessions_job_id_fkey", "job_id"),
    ("timeline_events", "timeline_events_job_id_fkey", "job_id"),
]

POLICIES = [
    ("submissions", "submissions_tenant_access"),
    ("similarity_results", "similarity_results_tenant_access"),
    ("webhook_events", "webhook_events_tenant_access"),
]

POLICY_SQL = {
    "submissions_tenant_access": """
        CREATE POLICY submissions_tenant_access ON submissions
        FOR ALL USING (job_id IN (
            SELECT id FROM jobs WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid
        ))
    """,
    "similarity_results_tenant_access": """
        CREATE POLICY similarity_results_tenant_access ON similarity_results
        FOR ALL USING (job_id IN (
            SELECT id FROM jobs WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid
        ))
    """,
    "webhook_events_tenant_access": """
        CREATE POLICY webhook_events_tenant_access ON webhook_events
        FOR ALL USING (job_id IN (
            SELECT id FROM jobs WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid
        ))
    """,
}


def _existing_tables() -> set:
    """Tables currently present in the public schema."""
    rows = (
        op.get_bind()
        .execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        .fetchall()
    )
    return {row[0] for row in rows}


def _drop_policies(present: set) -> None:
    """Drop RLS policies that reference jobs.id via subquery."""
    for table, policy in POLICIES:
        if table in present:
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")


def _recreate_policies(present: set) -> None:
    """Recreate the RLS policies dropped by _drop_policies()."""
    for table, policy in POLICIES:
        if table in present:
            op.execute(POLICY_SQL[policy])


def _drop_fks(present: set) -> None:
    """Drop foreign keys referencing jobs.id."""
    for table, constraint, _ in FOREIGN_KEYS:
        if table in present:
            op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")


def _recreate_fks(present: set) -> None:
    """Recreate the foreign keys referencing jobs.id."""
    for table, constraint, column in FOREIGN_KEYS:
        if table in present:
            op.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
                f"FOREIGN KEY ({column}) REFERENCES jobs(id)"
            )


def upgrade() -> None:
    present = _existing_tables()
    _drop_policies(present)
    _drop_fks(present)

    # Alter FK columns before jobs.id so the FK stays type-compatible.
    for table, _, column in FOREIGN_KEYS:
        if table in present:
            op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(36)")

    op.execute("ALTER TABLE jobs ALTER COLUMN id TYPE VARCHAR(36)")
    op.execute("ALTER TABLE jobs ALTER COLUMN id DROP DEFAULT")

    _recreate_fks(present)
    _recreate_policies(present)


def downgrade() -> None:
    present = _existing_tables()
    _drop_policies(present)
    _drop_fks(present)

    # Casting back to UUID only succeeds when every stored id is a valid UUID.
    # 8-char short ids cannot be cast, so remove those rows first (destructive).
    short_shape = "~ '^[a-fA-F0-9]{8}$'"
    op.execute(f"DELETE FROM jobs WHERE id {short_shape}")
    for table, _, column in FOREIGN_KEYS:
        if table in present:
            op.execute(f"DELETE FROM {table} WHERE {column}::text {short_shape}")

    op.execute("ALTER TABLE jobs ALTER COLUMN id TYPE UUID USING id::uuid")
    op.execute("ALTER TABLE jobs ALTER COLUMN id SET DEFAULT uuid_generate_v4()")

    for table, _, column in FOREIGN_KEYS:
        if table in present:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} TYPE UUID "
                f"USING {column}::uuid"
            )

    _recreate_fks(present)
    _recreate_policies(present)
