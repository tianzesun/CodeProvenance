"""add weight_audit table

Revision ID: r1s2t3u4v5w6
Revises: p4q5r6s7t8u9
Create Date: 2026-10-14 00:00:00.000000

Tamper-evident log of default fusion-weight governance events (weight
updates, validation evidence, reverts to shipped defaults) so audits do
not depend on a YAML file on local disk. Made idempotent so it can run
safely against either a fresh or partially migrated schema.

NOTE: the history already had three heads when this was added
(63ec37bd543d, p4q5r6s7t8u9, f2a3b4c5d6e7); this chains off the newest one.
A future merge-heads pass is still worthwhile but out of scope here.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "r1s2t3u4v5w6"
down_revision = "p4q5r6s7t8u9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS weight_audit (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            action VARCHAR(40) NOT NULL,
            actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            weights_before JSONB,
            weights_after JSONB,
            evidence JSONB,
            allowed BOOLEAN,
            note TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT ck_weight_audit_action CHECK (
                action IN ('weights_updated', 'evidence_attached', 'reverted_to_defaults')
            )
        )
    """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_weight_audit_created_at
        ON weight_audit (created_at)
    """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_weight_audit_action
        ON weight_audit (action)
    """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_weight_audit_action")
    op.execute("DROP INDEX IF EXISTS idx_weight_audit_created_at")
    op.execute("DROP TABLE IF EXISTS weight_audit")
