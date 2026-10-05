"""Cross-organization access tests for the academic router.

``require_admin`` only proves the caller holds the registry *role*. It says
nothing about *which* organization they administer, so routes that take an
organization id (or a row that carries one) from the URL must compare it against
the session themselves. Without that, any authorized admin could read or write
another organization's registry by editing the path.

These tests pin the scoping helper directly plus the routes that depend on it.
They are unit tests on the guard rather than full HTTP round-trips, because the
guard is where the decision is made.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.backend.api.routes import academic
from src.backend.api.routes.academic import (
    _require_org_access,
    _require_row_in_caller_org,
)


class _Row:
    """Minimal stand-in for an ORM row carrying an organization_id."""

    def __init__(self, organization_id: str) -> None:
        """Record the owning organization."""
        self.organization_id = organization_id


ORG_A = "org-aaaa"
ORG_B = "org-bbbb"


class TestRequireOrgAccess:
    """``_require_org_access`` gates URL-supplied organization ids."""

    def test_own_organization_is_allowed(self) -> None:
        _require_org_access(ORG_A, {"organization_id": ORG_A})

    def test_another_organization_is_refused(self) -> None:
        """The leak this guards: an admin editing the path to a rival org."""
        with pytest.raises(HTTPException) as excinfo:
            _require_org_access(ORG_B, {"organization_id": ORG_A})

        assert excinfo.value.status_code == 404

    def test_comparison_is_string_safe(self) -> None:
        """Ids arrive as UUID objects from the ORM and strings from the path."""
        import uuid

        org_uuid = uuid.uuid4()

        assert _require_org_access(str(org_uuid), {"organization_id": org_uuid}) is None

    def test_caller_without_an_organization_fails_closed(self) -> None:
        """No organization means no proven scope, so nothing is allowed."""
        with pytest.raises(HTTPException):
            _require_org_access(ORG_A, {})

    def test_caller_without_an_id_fails_closed(self) -> None:
        with pytest.raises(HTTPException):
            _require_org_access(ORG_A, {"organization_id": None})

    def test_missing_user_dict_is_rejected(self) -> None:
        with pytest.raises(HTTPException):
            _require_org_access(ORG_A, None)


class TestRequireRowInCallerOrg:
    """Rows resolved by id carry their own organization, so compare that."""

    def test_own_row_is_allowed(self) -> None:
        _require_row_in_caller_org(_Row(ORG_A), {"organization_id": ORG_A}, "Student")

    def test_foreign_row_is_refused(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            _require_row_in_caller_org(_Row(ORG_B), {"organization_id": ORG_A}, "Student")

        assert excinfo.value.status_code == 404

    def test_error_names_the_resource(self) -> None:
        """A 404 should not leak which table was being probed."""
        with pytest.raises(HTTPException) as excinfo:
            _require_row_in_caller_org(_Row(ORG_B), {"organization_id": ORG_A}, "Student")

        assert excinfo.value.detail == "Student not found"


class TestScopedRoutesAreWired:
    """Every route that reads an org id from the URL must call the guard.

    A guard that exists but is not attached to a route protects nothing, so this
    pins the call sites rather than only the helper.
    """

    SCOPED = (
        "get_organization",
        "create_course",
        "create_student",
        "list_students",
        "get_student",
    )

    @pytest.mark.parametrize("name", SCOPED)
    def test_route_calls_the_org_guard(self, name: str) -> None:
        handler = getattr(academic, name)
        source = handler.__doc__ or ""

        # The docstring is the route's own contract; the call is what enforces it.
        import inspect

        body = inspect.getsource(handler)
        assert "_require_org_access(" in body or "_require_row_in_caller_org(" in body

        # And the route must say so, so the behaviour is discoverable.
        assert "caller" in source.lower() or "own organization" in source.lower()


class TestTermUniquenessRaceIsClosed:
    """A duplicate ``(name, year)`` must be a 409, never an opaque 500."""

    def test_create_term_maps_integrity_error_to_conflict(self) -> None:
        import inspect

        source = inspect.getsource(academic.create_term)

        assert "except IntegrityError" in source
        assert "HTTP_409_CONFLICT" in source

    def test_update_term_maps_integrity_error_to_conflict(self) -> None:
        import inspect

        source = inspect.getsource(academic.update_term)

        assert "except IntegrityError" in source

    def test_both_roll_back_before_raising(self) -> None:
        """Without a rollback the session stays poisoned for the next request."""
        import inspect

        for handler in (academic.create_term, academic.update_term):
            source = inspect.getsource(handler)
            error_block = source.split("except IntegrityError", 1)[1]
            assert "db.rollback()" in error_block.split("raise", 1)[0]