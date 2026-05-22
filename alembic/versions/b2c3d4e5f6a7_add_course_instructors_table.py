"""add_course_instructors_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21

Adds the course_instructors join table for proper many-to-many
association between courses and instructors (professors).

This enables fine-grained course visibility: a user can see a course
if they are explicitly assigned as an instructor, or if they belong
to the same organization.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'course_instructors',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('course_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True, server_default='instructor'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('course_id', 'user_id', name='uq_course_instructor'),
    )

    op.create_index('idx_course_instructors_course', 'course_instructors', ['course_id'])
    op.create_index('idx_course_instructors_user', 'course_instructors', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_course_instructors_user', table_name='course_instructors')
    op.drop_index('idx_course_instructors_course', table_name='course_instructors')
    op.drop_table('course_instructors')
