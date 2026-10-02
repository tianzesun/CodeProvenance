"""add_user_verification_columns

Revision ID: p4q5r6s7t8u9
Revises: 612127788e79
Create Date: 2026-10-02

Self-service registration keeps a new account ``is_active=False`` until
its inbox redeems a single-use link. The token lives on the user row,
mirroring the password-reset pair:

* ``users.verify_token`` (nullable ``VARCHAR(255)``)
* ``users.verify_token_expires`` (nullable ``TIMESTAMP WITH TIME ZONE``)

Purely additive: existing rows keep ``NULL`` and behave exactly as
before, so the rollback just drops the two columns.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "p4q5r6s7t8u9"
down_revision = "612127788e79"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the email-verification token columns (idempotent)."""
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token VARCHAR(255)")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_token_expires "
        "TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    """Drop the verification columns (rollback)."""
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS verify_token_expires")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS verify_token")
