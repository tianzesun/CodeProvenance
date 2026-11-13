"""The rule the institution-membership migration and dry run share."""

from src.backend.infrastructure.institution_membership import (
    DEFAULT_INSTITUTION_NAME,
    Organization,
    UserRow,
    email_domain,
    parse_domains,
    plan_membership,
)

UOFT = frozenset({"utoronto.ca"})


def _user(n: int, email: str, *, active=True, org=None) -> UserRow:
    return UserRow(f"u{n}", email, active, org)


def test_domains_are_normalised() -> None:
    assert parse_domains(" UToronto.ca, @mail.utoronto.ca ,, ") == {
        "utoronto.ca",
        "mail.utoronto.ca",
    }
    assert parse_domains(None) == frozenset()
    assert email_domain("Prof@UToronto.CA") == "utoronto.ca"
    assert email_domain("not-an-email") == ""


def test_only_active_listed_domain_users_without_an_org_join() -> None:
    users = [
        _user(1, "a@utoronto.ca"),
        _user(2, "b@gmail.com"),  # outsider: waits for an admin
        _user(3, "c@utoronto.ca", active=False),  # inactive
        _user(4, "d@utoronto.ca", org="other"),  # already a member somewhere
        _user(5, "e@sub.utoronto.ca"),  # subdomain is a different domain
    ]
    plan = plan_membership([Organization("o1", "Demo University")], users, None, UOFT)

    assert plan.join_user_ids == ["u1"]
    assert plan.organization_id == "o1" and not plan.rename_to


def test_the_existing_organization_is_renamed_not_replaced() -> None:
    plan = plan_membership(
        [Organization("o1", "Demo University")], [], "University of Toronto", UOFT
    )

    assert (plan.organization_id, plan.create_name) == ("o1", "")
    assert (plan.rename_from, plan.rename_to) == (
        "Demo University",
        "University of Toronto",
    )


def test_with_no_organization_one_is_created() -> None:
    assert plan_membership([], [], "UofT", UOFT).create_name == "UofT"
    assert plan_membership([], [], "  ", UOFT).create_name == DEFAULT_INSTITUTION_NAME


def test_no_domains_means_nobody_joins() -> None:
    plan = plan_membership([], [_user(1, "a@utoronto.ca")], None, frozenset())

    assert plan.join_user_ids == []
    assert any("INSTITUTION_EMAIL_DOMAINS" in note for note in plan.notes)


def test_several_organizations_change_nothing() -> None:
    plan = plan_membership(
        [Organization("o1", "A"), Organization("o2", "B")],
        [_user(1, "a@utoronto.ca")],
        "X",
        UOFT,
    )

    assert plan.skip_reason
    assert not plan.join_user_ids and not plan.rename_to and not plan.create_name
