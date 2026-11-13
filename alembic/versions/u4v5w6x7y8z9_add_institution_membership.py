"""add institution membership

Revision ID: u4v5w6x7y8z9
Revises: t3u4v5w6x7y8
Create Date: 2026-11-13 00:00:00.000000

No path in the product ever set users.organization_id, so sharing, the colleague
list and term/course creation failed for every account it created
(docs/ORGANIZATION_MEMBERSHIP_DESIGN.md). This picks the deployment's one
organization (creating it, or renaming it from INSTITUTION_NAME) and joins active
users whose email domain is in INSTITUTION_EMAIL_DOMAINS. Nobody else is moved,
and nobody who already has an organization.

Data only. Every change is recorded in institution_membership_log so the
downgrade reverses exactly that: the joined users lose the organization again, a
rename is undone, and an organization this created is deleted if nothing else
uses it. With more than one organization it changes nothing and says so (a
failed migration would block every deploy). Safe to re-run.
"""

import logging
import os

import sqlalchemy as sa

from alembic import op

# The one rule shared with scripts/institution_membership_dry_run.py and the tests.
# That module says it must not change under this migration.
from src.backend.infrastructure.institution_membership import (
    Organization,
    UserRow,
    parse_domains,
    plan_membership,
)

# revision identifiers, used by Alembic.
revision = "u4v5w6x7y8z9"
down_revision = "t3u4v5w6x7y8"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS institution_membership_log (
            id SERIAL PRIMARY KEY,
            kind VARCHAR(20) NOT NULL,
            organization_id UUID NOT NULL,
            user_id UUID,
            previous_name VARCHAR(255),
            CONSTRAINT ck_institution_membership_log_kind CHECK (
                kind IN ('joined', 'created_org', 'renamed_org')
            )
        )
    """
    )
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT count(*) FROM institution_membership_log")
    ).scalar():
        log.info("Institution membership already applied; nothing to do.")
        return

    organizations = [
        Organization(str(row.id), row.name)
        for row in bind.execute(sa.text("SELECT id, name FROM organizations"))
    ]
    users = [
        UserRow(str(row.id), row.email, bool(row.is_active), row.organization_id)
        for row in bind.execute(
            sa.text("SELECT id, email, is_active, organization_id FROM users")
        )
    ]
    plan = plan_membership(
        organizations,
        users,
        os.environ.get("INSTITUTION_NAME"),
        parse_domains(os.environ.get("INSTITUTION_EMAIL_DOMAINS")),
    )
    if plan.skip_reason:
        log.warning("Institution membership skipped: %s", plan.skip_reason)
        return

    org_id = plan.organization_id
    if org_id is None:
        org_id = str(
            bind.execute(
                sa.text("INSERT INTO organizations (name) VALUES (:name) RETURNING id"),
                {"name": plan.create_name},
            ).scalar()
        )
        bind.execute(
            sa.text(
                "INSERT INTO institution_membership_log (kind, organization_id) "
                "VALUES ('created_org', :org)"
            ),
            {"org": org_id},
        )
        log.info("Created organization %r.", plan.create_name)
    elif plan.rename_to:
        bind.execute(
            sa.text(
                "UPDATE organizations SET name = :name, updated_at = now() WHERE id = :org"
            ),
            {"name": plan.rename_to, "org": org_id},
        )
        bind.execute(
            sa.text(
                "INSERT INTO institution_membership_log (kind, organization_id, previous_name) "
                "VALUES ('renamed_org', :org, :previous)"
            ),
            {"org": org_id, "previous": plan.rename_from},
        )
        log.info("Renamed organization %r to %r.", plan.rename_from, plan.rename_to)

    for user_id in plan.join_user_ids:
        bind.execute(
            sa.text("UPDATE users SET organization_id = :org WHERE id = :user"),
            {"org": org_id, "user": user_id},
        )
        bind.execute(
            sa.text(
                "INSERT INTO institution_membership_log (kind, organization_id, user_id) "
                "VALUES ('joined', :org, :user)"
            ),
            {"org": org_id, "user": user_id},
        )
    log.info("Joined %d existing user(s) to the organization.", len(plan.join_user_ids))
    for note in plan.notes:
        log.info(note)


def downgrade() -> None:
    op.execute(
        """
        UPDATE users u SET organization_id = NULL
        FROM institution_membership_log l
        WHERE l.kind = 'joined' AND l.user_id = u.id
          AND u.organization_id = l.organization_id
    """
    )
    op.execute(
        """
        UPDATE organizations o SET name = l.previous_name, updated_at = now()
        FROM institution_membership_log l
        WHERE l.kind = 'renamed_org' AND l.organization_id = o.id
    """
    )
    # Delete an organization this migration created, unless something now uses
    # it (courses or terms made after the upgrade): then it is left in place.
    op.execute(
        """
        DO $$
        BEGIN
            DELETE FROM organizations o
            USING institution_membership_log l
            WHERE l.kind = 'created_org' AND l.organization_id = o.id;
        EXCEPTION WHEN foreign_key_violation THEN
            RAISE NOTICE 'Organization created by this migration is in use; kept.';
        END $$;
    """
    )
    op.execute("DROP TABLE IF EXISTS institution_membership_log")
