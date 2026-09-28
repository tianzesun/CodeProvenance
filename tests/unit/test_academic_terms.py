"""Tests for the academic terms registry and course-term resolution.

Covers the term CRUD helpers, the newest-first/seasonal ordering, and the
``resolve_course_term`` rules that link a course to a registry entry while
falling back to free text for unregistered terms.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.backend.api.routes.academic import (
    TERM_SEASON_RANK,
    _term_sort_key,
    resolve_course_term,
    term_label,
)

ORG_ID = "org-123"


class _FakeQuery:
    """Minimal stand-in for a SQLAlchemy query used by ``resolve_course_term``."""

    def __init__(self, result):
        self._result = result
        self._filters: list = []

    def filter(self, *args):
        self._filters.append(args)
        return self

    def first(self):
        return self._result


class _FakeDb:
    """Fake session that returns a preset term for ``Term`` lookups."""

    def __init__(self, term=None):
        self._term = term
        self.queries: list[_FakeQuery] = []

    def query(self, _model):
        query = _FakeQuery(self._term)
        self.queries.append(query)
        return query


def _term(name: str, year: int, organization_id: str = ORG_ID) -> SimpleNamespace:
    """Build a stand-in for a ``Term`` row owned by ``organization_id``."""
    return SimpleNamespace(
        id=f"term-{name}-{year}", name=name, year=year, organization_id=organization_id
    )


def test_term_label_formats_name_and_year() -> None:
    """A term renders as 'Fall 2026', title-casing the season name."""
    assert term_label("Fall", 2026) == "Fall 2026"
    assert term_label("  spring ", 2027) == "Spring 2027"


def test_term_sort_key_orders_newest_first_then_by_season() -> None:
    """Terms sort newest year first, then Winter->Spring->Summer->Fall."""
    terms = [
        _term("Fall", 2026),
        _term("Winter", 2027),
        _term("Spring", 2027),
        _term("Fall", 2025),
        _term("Summer", 2027),
    ]
    ordered = [t.name for t in sorted(terms, key=_term_sort_key)]
    assert ordered == ["Winter", "Spring", "Summer", "Fall", "Fall"]
    # The 2026 Fall sorts above the 2025 Fall despite a later season rank.
    assert sorted(terms, key=_term_sort_key)[-1].year == 2025


def test_term_sort_key_places_unknown_seasons_last() -> None:
    """An unrecognized season name ranks after the four known ones."""
    assert _term_sort_key(_term("Midsummer", 2026)) == (-2026, 99, "Midsummer")
    assert TERM_SEASON_RANK["fall"] == TERM_SEASON_RANK["autumn"]


def test_resolve_term_uses_term_id_and_mirrors_name_and_year() -> None:
    """A term_id wins, and the course's term/year mirror the registry entry."""
    db = _FakeDb(_term("Fall", 2026))
    term_id, name, year = resolve_course_term(db, ORG_ID, "term-id", "ignored", 1999)
    assert term_id == "term-Fall-2026"
    assert name == "Fall"
    assert year == 2026


def test_resolve_term_rejects_unknown_term_id() -> None:
    """A dangling term_id raises 404 rather than silently dropping the term."""
    db = _FakeDb(None)
    with pytest.raises(HTTPException) as exc:
        resolve_course_term(db, ORG_ID, "missing", "Fall", 2026)
    assert exc.value.status_code == 404


def test_resolve_term_rejects_term_from_another_org() -> None:
    """A term_id owned by a different organization is a 403."""
    db = _FakeDb(_term("Fall", 2026, organization_id="other-org"))
    with pytest.raises(HTTPException) as exc:
        resolve_course_term(db, ORG_ID, "t1", None, None)
    assert exc.value.status_code == 403


def test_resolve_term_links_existing_registry_entry_by_name_and_year() -> None:
    """A free-text (term, year) pair that matches the registry gets linked."""
    db = _FakeDb(_term("Fall", 2026))
    term_id, name, year = resolve_course_term(db, ORG_ID, None, "fall", 2026)
    assert term_id == "term-Fall-2026"
    assert (name, year) == ("Fall", 2026)


def test_resolve_term_keeps_unregistered_term_as_free_text() -> None:
    """An unknown term/year pair is stored without a registry link."""
    db = _FakeDb(None)
    term_id, name, year = resolve_course_term(db, ORG_ID, None, "Winter", 2030)
    assert term_id is None
    assert (name, year) == ("Winter", 2030)


def test_resolve_term_without_name_or_year_is_unlinked() -> None:
    """Missing term metadata never produces a registry link."""
    db = _FakeDb(_term("Fall", 2026))
    assert resolve_course_term(db, ORG_ID, None, None, None) == (None, None, None)
    assert resolve_course_term(db, ORG_ID, None, "Fall", None) == (None, "Fall", None)
    assert resolve_course_term(db, ORG_ID, None, "   ", 2026) == (None, None, 2026)


# ---------------------------------------------------------------------------
# Schema-drift regressions
#
# ``assignment_versions`` was declared on the ORM model but never migrated,
# which made every assignment delete fail with UndefinedTable. These tests pin
# the ORM/DDL contract so the drift cannot silently return.
# ---------------------------------------------------------------------------


def test_assignment_versions_table_exists_in_orm_metadata() -> None:
    """The AssignmentVersion model is registered on the shared metadata."""
    from src.backend.config.database import Base

    assert "assignment_versions" in Base.metadata.tables


def test_assignment_versions_columns_match_orm_columns() -> None:
    """The migration's column set matches the model, with no drift either way."""
    from src.backend.models.database import AssignmentVersion

    columns = {c.name for c in AssignmentVersion.__table__.columns}
    expected = {
        "id",
        "assignment_id",
        "course_id",
        "version",
        "name",
        "description",
        "starter_files",
        "settings",
        "created_at",
        "is_active",
    }
    assert columns == expected


def test_assignment_versions_has_one_row_per_version() -> None:
    """(assignment_id, version) is unique so concurrent creates cannot dupe."""
    from src.backend.models.database import AssignmentVersion

    constraints = {
        c.name: tuple(col.name for col in c.columns)
        for c in AssignmentVersion.__table__.constraints
        if c.name
    }
    assert constraints.get("uq_assignment_versions_assignment_version") == (
        "assignment_id",
        "version",
    )


def test_assignment_versions_cascade_deletes() -> None:
    """Both FKs cascade, so deleting a parent removes its versions."""
    from src.backend.models.database import AssignmentVersion

    fks = {
        fk.parent.name: fk.ondelete for fk in AssignmentVersion.__table__.foreign_keys
    }
    assert fks == {"assignment_id": "CASCADE", "course_id": "CASCADE"}


def test_assignment_versions_relationship_deletes_children() -> None:
    """``versions`` must use delete-orphan cascade.

    Without it SQLAlchemy unlinks children on parent delete by setting their
    FK to NULL, which raises NotNullViolation against the database.
    """
    from src.backend.models.database import Assignment

    versions = Assignment.__mapper__.relationships["versions"]
    assert "delete-orphan" in versions.cascade
    # passive_deletes lets the DB-level ON DELETE CASCADE handle it.
    assert versions.passive_deletes is True


def test_get_versions_for_assignment_filters_by_assignment_not_course() -> None:
    """The list-versions endpoint must scope by assignment_id.

    It previously called the course-scoped helper, so it filtered on
    ``course_id`` using an assignment id and always returned nothing.
    """
    from src.backend.application.services.student_service import (
        AssignmentVersionService,
    )

    calls = {}

    class _Q:
        def filter(self, *args):
            calls["args"] = args
            return self

        def order_by(self, *a):
            return self

        def all(self):
            return []

    class _Db:
        def query(self, _m):
            return _Q()

    AssignmentVersionService.get_versions_for_assignment(_Db(), "assignment-1")
    assert len(calls["args"]) == 1


# ---------------------------------------------------------------------------
# Analytics overview helpers
#
# These guard three real defects in ``/api/analytics/overview``:
#   1. the endpoint had no tenant filter and leaked every organization's cases;
#   2. duplicate course codes across terms collapsed into one misleading bar;
#   3. the term/month series were in dict-insertion order, so the
#      previous-vs-current trend compared arbitrary terms.
# ---------------------------------------------------------------------------


def test_analytics_term_label_maps_calendar_months() -> None:
    """Calendar months map onto all four seasons the product supports.

    Regression: this emitted only Winter/Summer/Fall, so April-June cases were
    mislabelled as Winter and every spring course was misattributed.
    """
    from src.backend.api.server import _analytics_term_label

    assert _analytics_term_label(datetime(2026, 1, 15)) == "Winter 2026"
    assert _analytics_term_label(datetime(2026, 3, 31)) == "Winter 2026"
    assert _analytics_term_label(datetime(2026, 4, 1)) == "Spring 2026"
    assert _analytics_term_label(datetime(2026, 6, 15)) == "Spring 2026"
    assert _analytics_term_label(datetime(2026, 7, 15)) == "Summer 2026"
    assert _analytics_term_label(datetime(2026, 8, 31)) == "Summer 2026"
    assert _analytics_term_label(datetime(2026, 9, 1)) == "Fall 2026"
    assert _analytics_term_label(datetime(2026, 12, 31)) == "Fall 2026"
    assert _analytics_term_label(None) == "—"


def test_analytics_term_seasons_match_frontend_registry() -> None:
    """The backend can emit every season the frontend term UI offers.

    Guards the drift where analytics knew only three seasons while the term
    registry, course form and admin department list all offered four.
    """
    from src.backend.api.server import _analytics_term_label

    seasons = {
        _analytics_term_label(datetime(2026, month, 15)).split()[0]
        for month in range(1, 13)
    }
    assert seasons == {"Winter", "Spring", "Summer", "Fall"}


def test_analytics_term_sort_key_is_chronological() -> None:
    """Terms sort by year then season, not by insertion order.

    Regression: every label used to key to ``(0, 0)`` because the year was read
    from the wrong side of the split.
    """
    from src.backend.api.server import _analytics_term_sort_key

    labels = ["Fall 2026", "Winter 2026", "Summer 2026", "Winter 2027", "Fall 2025"]
    assert sorted(labels, key=_analytics_term_sort_key) == [
        "Fall 2025",
        "Winter 2026",
        "Summer 2026",
        "Fall 2026",
        "Winter 2027",
    ]


def test_analytics_term_sort_key_handles_placeholder_and_junk() -> None:
    """The "—" placeholder and unparseable labels degrade to a stable key."""
    from src.backend.api.server import _analytics_term_sort_key

    assert _analytics_term_sort_key("—") == (0, 0)
    assert _analytics_term_sort_key("nonsense") == (0, 0)
    assert _analytics_term_sort_key("Term 20x6") == (0, 0)


def test_analytics_month_sort_key_is_chronological() -> None:
    """Month labels sort oldest-to-newest and junk degrades safely."""
    from src.backend.api.server import _analytics_month_sort_key

    labels = ["Jun 2026", "Feb 2026", "Dec 2025", "bad"]
    assert sorted(labels, key=_analytics_month_sort_key) == [
        "bad",
        "Dec 2025",
        "Feb 2026",
        "Jun 2026",
    ]


def test_course_term_label_for_analytics() -> None:
    """Course term text renders as 'Fall 2026' or '—' when unset."""
    from src.backend.api.server import course_term_label_for_analytics

    course = SimpleNamespace(term="Fall", year=2026)
    assert course_term_label_for_analytics(course) == "Fall 2026"
    assert course_term_label_for_analytics(SimpleNamespace(term=None, year=None)) == "—"
    assert (
        course_term_label_for_analytics(SimpleNamespace(term="Fall", year=None))
        == "Fall"
    )
    assert course_term_label_for_analytics(None) == "—"


def test_empty_analytics_overview_is_all_zero() -> None:
    """A user with no visible courses gets honest zeros, not global figures."""
    from src.backend.api.server import _empty_analytics_overview

    payload = _empty_analytics_overview()
    assert payload["summary"] == {
        "total_cases": 0,
        "open_cases": 0,
        "courses_affected": 0,
        "high_priority": 0,
        "repeats": 0,
        "trend_change": None,
    }
    for key in (
        "cases_by_course",
        "semester_risk",
        "repeat_offenders",
        "suspicion_trend",
    ):
        assert payload[key] == []
    assert len(payload["insights"]) == 3


def test_analytics_endpoint_requires_authentication() -> None:
    """The endpoint must reject anonymous callers."""
    import inspect

    from src.backend.api.server import get_analytics_overview

    source = inspect.getsource(get_analytics_overview)
    assert "_require_current_user(request)" in source


def test_analytics_endpoint_scopes_cases_to_visible_courses() -> None:
    """Cases must be filtered to assignments of visible courses.

    Regression: the handler loaded ``db.query(Case).all()``, so a professor
    saw every organization's case counts and course names.
    """
    import inspect

    from src.backend.api.server import get_analytics_overview

    source = inspect.getsource(get_analytics_overview)
    # No unscoped global loads of tenant-owned tables.
    assert "db.query(Case).all()" not in source
    assert "db.query(Course).all()" not in source
    # Cases are narrowed through the visible assignment set.
    assert "Case.assignment_id.in_" in source
    # Links are narrowed to the visible case set.
    assert "CaseResultLink.case_id.in_" in source


def test_analytics_course_labels_include_term() -> None:
    """Course labels disambiguate same-code offerings by term.

    Regression: ``CSC108`` is offered in multiple terms, so keying on the bare
    code merged distinct course offerings into one bar.
    """
    import inspect

    from src.backend.api.server import get_analytics_overview

    source = inspect.getsource(get_analytics_overview)
    assert "course_term_label_for_analytics" in source
    assert "course.code or course.name" in source
