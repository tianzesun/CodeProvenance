"""Tests for admin bulk user import/export helpers.

Covers the pure parsing/formatting helpers behind
``GET /api/admin/users/export`` and ``POST /api/admin/users/import``: CSV and
JSON payloads must normalize into the same row shape, malformed input must
produce a clear error instead of raising, and exports must never leak
credential material.
"""

from types import SimpleNamespace

import pytest

from src.backend.api import server


class TestParseUserImportContent:
    """Files must normalize into row dicts with a stable 1-based row number."""

    def test_csv_rows_are_normalized(self) -> None:
        content = (
            "email,full_name,role\n"
            "  A@Example.EDU , Alice Smith , professor\n"
            "b@example.edu,Bob Jones,admin\n"
        )
        rows, errors = server._parse_user_import_content(content)

        assert errors == []
        assert len(rows) == 2
        assert rows[0]["__row__"] == 1
        assert rows[0]["email"] == "A@Example.EDU"
        assert rows[0]["full_name"] == "Alice Smith"
        assert rows[0]["role"] == "professor"
        assert rows[1]["__row__"] == 2

    def test_json_list_rows_are_parsed(self) -> None:
        content = '[{"email": "a@example.edu", "full_name": "Alice", "role": "admin"}]'
        rows, errors = server._parse_user_import_content(content)

        assert errors == []
        assert rows == [
            {
                "__row__": 1,
                "email": "a@example.edu",
                "full_name": "Alice",
                "role": "admin",
            }
        ]

    def test_json_object_with_users_key_is_accepted(self) -> None:
        content = '{"users": [{"email": "a@example.edu", "full_name": "Alice"}]}'
        rows, errors = server._parse_user_import_content(content)

        assert errors == []
        assert rows[0]["email"] == "a@example.edu"

    def test_columns_are_lowercased_and_spaces_become_underscores(self) -> None:
        content = '[{"Email": "a@example.edu", "Full Name": "Alice"}]'
        rows, errors = server._parse_user_import_content(content)

        assert errors == []
        assert rows[0]["email"] == "a@example.edu"
        assert rows[0]["full_name"] == "Alice"

    def test_single_json_object_without_users_key_is_rejected(self) -> None:
        # A bare object is ambiguous with the {"users": [...]} envelope, so it
        # must be reported rather than silently treated as one row.
        rows, errors = server._parse_user_import_content('{"email": "a@example.edu"}')

        assert rows == []
        assert errors and "JSON must be a list" in errors[0]

    def test_unknown_columns_are_tolerated(self) -> None:
        # Export files carry read-only audit columns; re-importing them must work.
        content = "email,full_name,created_at,last_login_at\na@example.edu,Alice,,\n"
        rows, errors = server._parse_user_import_content(content)

        assert errors == []
        assert rows[0]["email"] == "a@example.edu"

    def test_empty_content_reports_error(self) -> None:
        rows, errors = server._parse_user_import_content("   ")

        assert rows == []
        assert errors == ["The file is empty."]

    def test_invalid_json_reports_error(self) -> None:
        rows, errors = server._parse_user_import_content("{not json", "json")

        assert rows == []
        assert errors and "Invalid JSON" in errors[0]

    def test_json_without_user_list_reports_error(self) -> None:
        rows, errors = server._parse_user_import_content('{"users": 5}', "json")

        assert rows == []
        assert errors and "JSON must be a list" in errors[0]


class TestCoerceImportBool:
    """Spreadsheet-style booleans must map onto the account is_active flag."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, True),
            ("", True),
            (True, True),
            (False, False),
            ("TRUE", True),
            ("yes", True),
            ("1", True),
            ("inactive", False),
            ("0", False),
        ],
    )
    def test_values(self, raw: object, expected: bool) -> None:
        assert server._coerce_import_bool(raw, default=True) is expected


class TestUserExport:
    """Export output must be complete for auditing and free of secrets."""

    def test_export_rows_omit_credentials_and_include_tenant(self) -> None:
        entry = SimpleNamespace(
            email="a@example.edu",
            full_name="Alice",
            role="professor",
            is_active=True,
            tenant=SimpleNamespace(name="CS Workspace"),
            created_at=None,
            last_login_at=None,
        )
        rows = server._serialize_user_export([entry])

        assert rows[0]["tenant_name"] == "CS Workspace"
        assert rows[0]["created_at"] == ""
        assert "password_hash" not in rows[0]
        assert "reset_token" not in rows[0]

    def test_export_rows_tolerate_missing_tenant(self) -> None:
        entry = SimpleNamespace(
            email="a@example.edu",
            full_name="Alice",
            role="admin",
            is_active=False,
            tenant=None,
            created_at=None,
            last_login_at=None,
        )
        rows = server._serialize_user_export([entry])

        assert rows[0]["tenant_name"] == ""
        assert rows[0]["is_active"] is False

    def test_csv_has_header_and_no_password_column(self) -> None:
        csv_text = server._users_to_csv(
            [
                {
                    "email": "a@example.edu",
                    "full_name": "Alice",
                    "role": "professor",
                    "is_active": True,
                    "tenant_name": "CS",
                    "created_at": "",
                    "last_login_at": "",
                }
            ]
        )
        header = csv_text.splitlines()[0]

        assert header == (
            "email,full_name,role,is_active,tenant_name,created_at,last_login_at"
        )
        assert "password" not in csv_text.lower()

    def test_export_columns_exclude_credential_fields(self) -> None:
        for column in server.USER_EXPORT_COLUMNS:
            assert "password" not in column
            assert "token" not in column


class TestRoutesRegistered:
    """The import/export endpoints must exist on the admin users prefix."""

    def test_import_and_export_routes_exist(self) -> None:
        paths = {getattr(route, "path", "") for route in server.app.routes}

        assert "/api/admin/users/export" in paths
        assert "/api/admin/users/import" in paths
