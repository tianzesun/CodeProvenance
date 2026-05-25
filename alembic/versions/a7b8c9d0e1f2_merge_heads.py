"""merge heads for fpr_validation_runs

Revision ID: a7b8c9d0e1f2
Revises: 63ec37bd543d, f2a3b4c5d6e7
Create Date: 2026-05-24 19:10:00.000000

This is a merge migration to resolve the two heads after adding the
fpr_validation_runs table.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = ('63ec37bd543d', 'f2a3b4c5d6e7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
