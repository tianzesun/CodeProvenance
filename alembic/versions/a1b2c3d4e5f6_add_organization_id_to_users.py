"""add_organization_id_to_users

Revision ID: a1b2c3d4e5f6
Revises: 79d5f84bbaa5
Create Date: 2026-05-21

This migration adds organization_id to the users table so we can scope
courses and assignments to the user's organization (org-level visibility
for professors/instructors).

This is the first step toward proper multi-organization scoping while
keeping backward compatibility (nullable column).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '79d5f84bbaa5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add organization_id column to users (nullable for backward compatibility)
    op.add_column(
        'users',
        sa.Column('organization_id', postgresql.UUID(as_uuid=False), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_users_organization_id',
        'users',
        'organizations',
        ['organization_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Optional: add index for common query pattern (user + organization)
    op.create_index(
        'idx_users_organization',
        'users',
        ['organization_id']
    )


def downgrade() -> None:
    op.drop_index('idx_users_organization', table_name='users')
    op.drop_constraint('fk_users_organization_id', 'users', type_='foreignkey')
    op.drop_column('users', 'organization_id')
