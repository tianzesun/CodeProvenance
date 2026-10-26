"""add resource_shares table

Revision ID: s2t3u4v5w6x7
Revises: r1s2t3u4v5w6
Create Date: 2026-10-25 00:00:00.000000

Professors see only their own courses unless an owner shares: a course, job
or case can be shared with selected faculty or with the whole workspace.
Nothing is shared by default, so every existing item is private once this
ships. Only a new table is added; downgrade drops it and nothing else.
Idempotent like r1s2t3u4v5w6, so it is safe on a partially migrated schema.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "s2t3u4v5w6x7"
down_revision = "r1s2t3u4v5w6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_shares (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            resource_type VARCHAR(20) NOT NULL,
            resource_id VARCHAR(64) NOT NULL,
            shared_with_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            shared_with_workspace VARCHAR(64),
            granted_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT ck_resource_shares_resource_type CHECK (
                resource_type IN ('course', 'job', 'case')
            ),
            CONSTRAINT ck_resource_shares_one_audience CHECK (
                (shared_with_user_id IS NULL) <> (shared_with_workspace IS NULL)
            )
        )
    """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resource_shares_resource
        ON resource_shares (resource_type, resource_id)
    """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resource_shares_user
        ON resource_shares (shared_with_user_id)
    """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resource_shares_workspace
        ON resource_shares (shared_with_workspace)
    """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_shares_user
        ON resource_shares (resource_type, resource_id, shared_with_user_id)
        WHERE shared_with_user_id IS NOT NULL
    """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_shares_workspace
        ON resource_shares (resource_type, resource_id, shared_with_workspace)
        WHERE shared_with_workspace IS NOT NULL
    """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_resource_shares_workspace")
    op.execute("DROP INDEX IF EXISTS uq_resource_shares_user")
    op.execute("DROP INDEX IF EXISTS idx_resource_shares_workspace")
    op.execute("DROP INDEX IF EXISTS idx_resource_shares_user")
    op.execute("DROP INDEX IF EXISTS idx_resource_shares_resource")
    op.execute("DROP TABLE IF EXISTS resource_shares")
