"""Show what migration u4v5w6x7y8z9 would do, without changing anything.

Run on the deployment before ``alembic upgrade head``, with the same
INSTITUTION_NAME and INSTITUTION_EMAIL_DOMAINS the migration will see:

    INSTITUTION_EMAIL_DOMAINS=utoronto.ca python scripts/institution_membership_dry_run.py
    ... --list    # also print the addresses that would join

Read-only: it only runs SELECTs. Counts are printed by default; addresses only
with --list, since they are personal information.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from src.backend.config.database import SessionLocal
from src.backend.infrastructure.institution_membership import (
    Organization,
    UserRow,
    email_domain,
    parse_domains,
    plan_membership,
)


def main() -> int:
    """Print the plan; exit 1 when the migration would skip."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list", action="store_true", help="print addresses that would join"
    )
    args = parser.parse_args()
    domains = parse_domains(os.environ.get("INSTITUTION_EMAIL_DOMAINS"))

    with SessionLocal() as db:
        organizations = [
            Organization(str(r.id), r.name)
            for r in db.execute(text("SELECT id, name FROM organizations"))
        ]
        users = [
            UserRow(str(r.id), r.email, bool(r.is_active), r.organization_id)
            for r in db.execute(
                text("SELECT id, email, is_active, organization_id FROM users")
            )
        ]
    plan = plan_membership(
        organizations, users, os.environ.get("INSTITUTION_NAME"), domains
    )

    print(f"Organizations now: {[o.name for o in organizations] or 'none'}")
    active = [u for u in users if u.is_active]
    print(
        f"Active users: {len(active)} "
        f"({sum(1 for u in active if u.organization_id)} already in an organization)"
    )
    if plan.skip_reason:
        print(f"SKIP: {plan.skip_reason}")
        return 1
    if plan.create_name:
        print(f"Would create organization {plan.create_name!r}.")
    elif plan.rename_to:
        print(f"Would rename {plan.rename_from!r} to {plan.rename_to!r}.")
    else:
        print("Would keep the existing organization's name.")
    print(f"Domains: {sorted(domains) or 'none set'}")
    joining = set(plan.join_user_ids)
    by_domain = Counter(email_domain(u.email) for u in users if u.id in joining)
    print(f"Would join {len(joining)} user(s): {dict(by_domain) or '-'}")
    left_out = [u for u in active if not u.organization_id and u.id not in joining]
    print(
        f"Left for an admin to review: {len(left_out)} active user(s) outside those domains"
    )
    if args.list:
        for user in sorted(
            (u for u in users if u.id in joining), key=lambda u: u.email
        ):
            print(f"  join: {user.email}")
    for note in plan.notes:
        print(f"Note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
