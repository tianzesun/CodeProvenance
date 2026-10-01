"""Unit tests for the dashboard RBAC policy and its route wiring.

The permission matrix in ``src.backend.api.middleware.auth`` is the single
source of truth for what a dashboard role may do, and
``src.backend.application.services.academic_access`` owns the row-level detail
(which courses a professor may see and touch). These tests pin the product
contract that both halves implement:

* an **admin** creates users, terms and courses, binds a course to a term and
  assigns users to courses — but never authors an assignment;
* a **professor** authors the assignments of the courses they are assigned to
  (current and past terms) and cannot manage the registry;
* machine principals (API keys) and unknown roles hold no permissions at all.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.backend.api.middleware import auth
from src.backend.api.routes import academic
from src.backend.application.services import academic_access
from src.backend.models.database import Assignment, Course, CourseInstructor

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _RecordingQuery:
    """Minimal SQLAlchemy query stand-in recording filters and returning rows."""

    def __init__(self, rows: list | None = None) -> None:
        """Store the rows this query should return."""
        self.filters: list = []
        self._rows = list(rows or [])

    def filter(self, *criteria):
        """Record the criteria and return self so calls can be chained."""
        self.filters.extend(criteria)
        return self

    def first(self):
        """Return the first row, or None when the query would match nothing."""
        return self._rows[0] if self._rows else None


class _RecordingDb:
    """Session stand-in handing out a recorder per queried entity."""

    def __init__(self, rows_by_entity: dict | None = None) -> None:
        """Prepare lookups keyed by the queried SQLAlchemy attribute."""
        self.queried: list = []
        self.queries: list[_RecordingQuery] = []
        self._rows_by_entity = rows_by_entity or {}

    def query(self, *entities):
        """Record which entity was queried and return its recorder."""
        entity = entities[0]
        self.queried.append(entity)
        query = _RecordingQuery(self._rows_by_entity.get(entity))
        self.queries.append(query)
        return query


def _request_with(user: dict | None = None) -> SimpleNamespace:
    """Build a request stand-in carrying ``user`` on ``request.state``."""
    state = SimpleNamespace(user=user) if user else SimpleNamespace()
    return SimpleNamespace(state=state)


ADMIN_USER = {"id": "user-admin", "role": "admin", "organization_id": "org-1"}
PROFESSOR_USER = {"id": "user-prof", "role": "professor", "organization_id": "org-1"}


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------


def test_admin_owns_the_registry_but_not_assignments() -> None:
    """The admin role manages users/terms/courses/rosters, never assignments."""
    admin = auth.permissions_for_role("admin")
    assert {"user:manage", "term:manage", "course:manage", "roster:manage"} <= admin
    assert "course:read:all" in admin
    assert "assignment:manage" not in admin


def test_professor_owns_assignments_but_not_the_registry() -> None:
    """The professor role manages assignments, never registry entries."""
    professor = auth.permissions_for_role("professor")
    assert "assignment:manage" in professor
    assert "course:read:assigned" in professor
    registry = {"user:manage", "term:manage", "course:manage", "roster:manage"}
    assert not professor & registry


def test_machine_and_unknown_roles_hold_no_permissions() -> None:
    """API keys and unknown roles fail closed rather than opening the matrix."""
    for role in ("api", "root", "student", "", None):
        assert auth.permissions_for_role(role) == frozenset()
        assert auth.has_permission({"id": "x", "role": role}, "course:manage") is False


def test_permission_lookup_normalises_role_text() -> None:
    """Roles arrive from the database with mixed case/whitespace."""
    assert auth.has_permission({"role": "  Admin "}, "course:manage") is True
    assert auth.has_permission({"role": "PROFESSOR"}, "assignment:manage") is True


def test_dashboard_roles_cover_the_console() -> None:
    """Every advertised dashboard role is in the matrix and vice versa."""
    assert set(auth.DASHBOARD_ROLES) == set(auth.ROLE_PERMISSIONS)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def test_dashboard_user_requires_authentication() -> None:
    """A request with no resolved user is unauthenticated, not forbidden."""
    with pytest.raises(HTTPException) as excinfo:
        auth.dashboard_user(_request_with())
    assert excinfo.value.status_code == 401


def test_require_roles_accepts_allowlisted_role_and_rejects_others() -> None:
    """The role guard returns the caller only for allowlisted roles."""
    guard = auth.require_roles("admin")
    assert guard(_request_with(ADMIN_USER)) is ADMIN_USER

    with pytest.raises(HTTPException) as excinfo:
        guard(_request_with(PROFESSOR_USER))
    assert excinfo.value.status_code == 403


def test_require_roles_without_roles_is_a_programming_error() -> None:
    """A guard with no allowed role would deny everything: fail loudly."""
    with pytest.raises(ValueError):
        auth.require_roles()


def test_require_user_permission_follows_the_matrix() -> None:
    """Permission guards accept the granting role and reject the other one."""
    guard = auth.require_user_permission("course:manage")
    assert guard(_request_with(ADMIN_USER)) is ADMIN_USER

    with pytest.raises(HTTPException) as excinfo:
        guard(_request_with(PROFESSOR_USER))
    assert excinfo.value.status_code == 403
    assert "course:manage" in str(excinfo.value.detail)


def test_generated_dependencies_are_named_after_what_they_enforce() -> None:
    """Guard callables carry a readable name for diagnostics and tests."""
    assert auth.require_roles("admin").__name__ == "require_roles_admin"
    assert (
        auth.require_user_permission("term:manage").__name__
        == "require_user_permission_term_manage"
    )


# ---------------------------------------------------------------------------
# Row-level policy (academic_access)
# ---------------------------------------------------------------------------


def test_role_predicates_split_registry_from_teaching() -> None:
    """Registry and teaching predicates follow the matrix, not the role name."""
    assert academic_access.is_registry_admin(ADMIN_USER) is True
    assert academic_access.can_manage_assignments(ADMIN_USER) is False
    assert academic_access.is_registry_admin(PROFESSOR_USER) is False
    assert academic_access.can_manage_assignments(PROFESSOR_USER) is True


def test_admin_visibility_is_organization_wide() -> None:
    """An admin sees every course of their organization."""
    db = _RecordingDb()
    academic_access.visible_course_id_query(db, ADMIN_USER)
    assert db.queried == [Course.id]
    assert len(db.queries[0].filters) == 1
    assert "courses.organization_id" in str(db.queries[0].filters[0])


def test_admin_without_organization_is_not_narrowed() -> None:
    """A platform-wide admin (no organization) is not filtered at all."""
    db = _RecordingDb()
    academic_access.visible_course_id_query(db, {"id": "a", "role": "admin"})
    assert db.queries[0].filters == []


def test_professor_visibility_is_the_instructor_link_only() -> None:
    """A professor sees only courses a course_instructors row ties them to.

    Regression: the listings OR'ed in "same organization", so a professor saw
    the whole catalog instead of their own courses.
    """
    db = _RecordingDb()
    academic_access.visible_course_id_query(db, PROFESSOR_USER)
    assert db.queried == [CourseInstructor.course_id]
    assert len(db.queries[0].filters) == 1
    assert "course_instructors.user_id" in str(db.queries[0].filters[0])


def test_identity_less_callers_see_nothing() -> None:
    """No identity and no registry rights matches no rows, never all rows."""
    db = _RecordingDb()
    academic_access.visible_course_id_query(db, {"role": "api"})
    assert db.queried == [Course.id]
    assert "false" in str(db.queries[0].filters[0]).lower()


def test_admin_reads_any_course_of_their_organization() -> None:
    """Admins read their organization's courses and nothing else."""
    in_org = _RecordingDb({Course.id: ["course-1"]})
    assert academic_access.can_read_course(in_org, ADMIN_USER, "course-1") is True

    other_org = _RecordingDb()
    assert academic_access.can_read_course(other_org, ADMIN_USER, "course-9") is False
    applied = " ".join(str(criterion) for criterion in other_org.queries[0].filters)
    assert "courses.organization_id" in applied


def test_admin_without_organization_reads_without_a_lookup() -> None:
    """A platform-wide admin short-circuits to allowed."""
    db = _RecordingDb()
    assert (
        academic_access.can_read_course(db, {"id": "a", "role": "admin"}, "course-1")
        is True
    )
    assert db.queried == []


def test_professor_reads_only_assigned_courses() -> None:
    """Read access for a professor is the instructor link, nothing else."""
    linked = _RecordingDb({CourseInstructor.id: [SimpleNamespace(id="link-1")]})
    assert academic_access.can_read_course(linked, PROFESSOR_USER, "course-1") is True

    unlinked = _RecordingDb()
    assert (
        academic_access.can_read_course(unlinked, PROFESSOR_USER, "course-2") is False
    )


def test_managing_assignments_needs_the_role_right_and_the_course_link() -> None:
    """An admin is refused outright; a professor must teach the course."""
    admin_db = _RecordingDb({CourseInstructor.id: [SimpleNamespace(id="link-1")]})
    assert (
        academic_access.can_manage_course_assignments(admin_db, ADMIN_USER, "course-1")
        is False
    )
    assert admin_db.queried == []  # refused before touching the database

    linked = _RecordingDb({CourseInstructor.id: [SimpleNamespace(id="link-1")]})
    assert (
        academic_access.can_manage_course_assignments(
            linked, PROFESSOR_USER, "course-1"
        )
        is True
    )

    unlinked = _RecordingDb()
    assert (
        academic_access.can_manage_course_assignments(
            unlinked, PROFESSOR_USER, "course-2"
        )
        is False
    )


def test_instructor_lookup_short_circuits_without_ids() -> None:
    """A missing course id or user id is never an instructor link."""
    db = _RecordingDb()
    assert academic_access.is_course_instructor(db, PROFESSOR_USER, "") is False
    assert (
        academic_access.is_course_instructor(db, {"role": "professor"}, "c-1") is False
    )
    assert db.queried == []


def test_assignment_course_lookup_maps_and_misses() -> None:
    """The assignment → course lookup powers the /assignments/{id} guards."""
    # A single-column query returns a row tuple, exactly like SQLAlchemy.
    db = _RecordingDb({Assignment.course_id: [("course-1",)]})
    assert academic_access.course_id_for_assignment(db, "assignment-1") == "course-1"

    missing = _RecordingDb()
    assert academic_access.course_id_for_assignment(missing, "assignment-9") is None
    assert academic_access.course_id_for_assignment(missing, "") is None


# ---------------------------------------------------------------------------
# Route wiring
# ---------------------------------------------------------------------------


def _guarded_routes(router) -> dict[tuple[str, str], set[str]]:
    """Map ``(METHOD, path)`` to the names of the guards FastAPI attached."""
    guarded: dict[tuple[str, str], set[str]] = {}
    for route in router.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        names = {
            getattr(dependency.call, "__name__", "")
            for dependency in getattr(route.dependant, "dependencies", [])
        }
        for method in getattr(route, "methods", []) or []:
            guarded[(method, path)] = names
    return guarded


#: Registry writes are admin-only; assignment writes belong to the professor
#: teaching the course. Each entry names the guard that must protect the
#: endpoint, so a future refactor cannot silently drop one.
EXPECTED_ROUTE_GUARDS: dict[tuple[str, str], str] = {
    ("POST", "/api/terms"): "require_user_permission_term_manage",
    ("PUT", "/api/terms/{term_id}"): "require_user_permission_term_manage",
    ("DELETE", "/api/terms/{term_id}"): "require_user_permission_term_manage",
    ("POST", "/api/courses"): "require_user_permission_course_manage",
    ("PUT", "/api/courses/{course_id}"): "require_user_permission_course_manage",
    ("DELETE", "/api/courses/{course_id}"): "require_user_permission_course_manage",
    ("POST", "/api/courses/{course_id}/assignments"): "require_assignment_write_access",
    ("DELETE", "/api/assignments/{assignment_id}"): (
        "require_assignment_write_access_by_id"
    ),
    ("POST", "/api/assignments/{assignment_id}/versions"): (
        "require_assignment_write_access_by_id"
    ),
    ("POST", "/api/courses/{course_id}/enrollments"): (
        "require_user_permission_roster_manage"
    ),
    ("POST", "/api/organizations/{org_id}/students"): (
        "require_user_permission_roster_manage"
    ),
}


def test_academic_registry_and_assignment_routes_carry_their_guards() -> None:
    """Each academic write endpoint is protected by the RBAC guard it needs."""
    guarded = _guarded_routes(academic.router)
    missing = [
        f"{method} {path} (expected {guard})"
        for (method, path), guard in EXPECTED_ROUTE_GUARDS.items()
        if guard not in guarded.get((method, path), set())
    ]
    assert not missing, f"unguarded academic endpoints: {missing}"


def test_course_read_routes_use_the_scoped_read_guard() -> None:
    """Course-scoped reads resolve visibility instead of trusting any session."""
    guarded = _guarded_routes(academic.router)
    for method, path in (
        ("GET", "/api/courses/{course_id}"),
        ("GET", "/api/courses/{course_id}/assignments"),
        ("GET", "/api/courses/{course_id}/enrollments"),
    ):
        assert (
            "require_course_read_access" in guarded[(method, path)]
        ), f"{method} {path} is not read-scoped"


def test_dashboard_course_endpoints_share_one_visibility_policy() -> None:
    """The dashboard read endpoints delegate to ``academic_access``.

    Regression: /api/courses, /api/assignments and /api/courses/{id} each
    hand-rolled "instructor OR same organization", so a professor saw the whole
    catalog.
    """
    from src.backend.api import server

    handlers = (server.get_courses, server.get_assignments, server.get_course_detail)
    for handler in handlers:
        source = inspect.getsource(handler)
        assert "academic_access." in source, f"{handler.__name__} bypasses the policy"
    assert "academic_access.visible_course_id_query" in inspect.getsource(
        server.get_courses
    )
    assert "academic_access.visible_course_id_query" in inspect.getsource(
        server.get_assignments
    )
    assert "academic_access.can_read_course" in inspect.getsource(
        server.get_course_detail
    )
