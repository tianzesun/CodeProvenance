"""Who joins the institution's organization (docs/ORGANIZATION_MEMBERSHIP_DESIGN.md).

The decision is a pure function so the Alembic migration, the dry-run script and
the tests all apply the same rule: one organization per deployment, renamed from
``INSTITUTION_NAME`` if it exists, and only active users on the listed email
domains (``INSTITUTION_EMAIL_DOMAINS``) joined automatically. Everyone else waits
for an admin.

Migration ``u4v5w6x7y8z9`` imports this rule. Changing what it decides changes
what that migration would do on a fresh install, so a new rule needs a new
migration, not an edit here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_INSTITUTION_NAME = "Institution"


def parse_domains(raw: str | None) -> frozenset[str]:
    """``"utoronto.ca, mail.utoronto.ca"`` -> lower-cased domains, no "@" or blanks."""
    return frozenset(
        part.strip().lstrip("@").lower()
        for part in (raw or "").split(",")
        if part.strip()
    )


def email_domain(email: str | None) -> str:
    """The part after the last "@", lower-cased; "" for a malformed address."""
    text = (email or "").strip().lower()
    return text.rsplit("@", 1)[1] if "@" in text else ""


@dataclass(frozen=True)
class Organization:
    """An existing organization row."""

    id: str
    name: str


@dataclass(frozen=True)
class UserRow:
    """The user columns the decision needs."""

    id: str
    email: str
    is_active: bool
    organization_id: str | None


@dataclass
class MembershipPlan:
    """What the migration would do; ``skip_reason`` set means do nothing."""

    skip_reason: str = ""
    #: ``None`` when a new organization must be created.
    organization_id: str | None = None
    create_name: str = ""
    rename_from: str = ""
    rename_to: str = ""
    join_user_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def plan_membership(
    organizations: list[Organization],
    users: list[UserRow],
    institution_name: str | None,
    domains: frozenset[str],
) -> MembershipPlan:
    """Decide the organization and who joins it. Never moves an existing member."""
    name = (institution_name or "").strip()
    plan = MembershipPlan()
    if len(organizations) > 1:
        plan.skip_reason = (
            f"{len(organizations)} organizations exist; one organization per deployment "
            "is assumed, so nobody was moved. Assign members by hand."
        )
        return plan
    if organizations:
        org = organizations[0]
        plan.organization_id = org.id
        if name and name != org.name:
            plan.rename_from, plan.rename_to = org.name, name
    else:
        plan.create_name = name or DEFAULT_INSTITUTION_NAME
    if not domains:
        plan.notes.append(
            "INSTITUTION_EMAIL_DOMAINS is not set, so no existing user joined; "
            "admins add members from the admin page."
        )
        return plan
    plan.join_user_ids = sorted(
        user.id
        for user in users
        if user.is_active
        and not user.organization_id
        and email_domain(user.email) in domains
    )
    return plan
