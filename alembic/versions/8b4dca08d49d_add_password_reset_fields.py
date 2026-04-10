"""add_password_reset_fields

Revision ID: 8b4dca08d49d
Revises: 002
Create Date: 2026-04-10 09:52:39.719926

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b4dca08d49d'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add password reset fields to users table
    op.add_column('users', sa.Column('reset_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('reset_token_expires', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove password reset fields from users table
    op.drop_column('users', 'reset_token_expires')
    op.drop_column('users', 'reset_token')
