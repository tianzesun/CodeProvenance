"""add_organization_course_assignment_case_tables

Revision ID: YOUR_REVISION_ID
Revises: 8b4dca08d49d
Create Date: 2026-05-21 22:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '79d5f84bbaa5'
down_revision = '8b4dca08d49d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # organizations
    op.create_table('organizations',
        sa.Column('id', sa.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # courses
    op.create_table('courses',
        sa.Column('id', sa.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # assignments
    op.create_table('assignments',
        sa.Column('id', sa.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('course_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('due_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # cases
    op.create_table('cases',
        sa.Column('id', sa.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('assignment_id', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_by_id', sa.UUID(as_uuid=False), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # case_result_links
    op.create_table('case_result_links',
        sa.Column('id', sa.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('case_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('similarity_result_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['similarity_result_id'], ['similarity_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # case_comments
    op.create_table('case_comments',
        sa.Column('id', sa.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('case_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Add assignment_id to jobs table
    op.add_column('jobs', sa.Column('assignment_id', sa.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key(None, 'jobs', 'assignments', ['assignment_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'jobs', type_='foreignkey')
    op.drop_column('jobs', 'assignment_id')

    op.drop_table('case_comments')
    op.drop_table('case_result_links')
    op.drop_table('cases')
    op.drop_table('assignments')
    op.drop_table('courses')
    op.drop_table('organizations')
