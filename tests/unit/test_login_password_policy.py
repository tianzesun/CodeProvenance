"""Login must validate credentials, not password strength.

Password-strength policy belongs on the endpoints that *set* a password
(bootstrap-admin, create-user, reset-password). Enforcing it at login rejects
perfectly valid existing credentials — e.g. an account whose password predates
a policy change — with no way to fix it from the sign-in screen.
"""

from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.config.settings import settings


class TestLoginDoesNotEnforcePasswordPolicy:
    """The sign-in endpoint must reach the credential check for any password."""

    def test_weak_existing_password_is_not_rejected_by_policy(self, monkeypatch) -> None:
        """A stale-but-correct password reaches the hash comparison, not a 400."""
        # Force the policy active so the test fails if login consults it,
        # independent of how DEBUG_MODE happens to be configured.
        monkeypatch.setattr(settings, "DEBUG_MODE", False)
        monkeypatch.setattr(
            server,
            "_login_sync",
            lambda email, password: {"id": "u1", "email": email, "role": "professor"},
        )
        monkeypatch.setattr(
            server, "_get_user_for_cookie", lambda email: {"id": "u1", "email": email}
        )
        monkeypatch.setattr(server, "_issue_auth_cookie", lambda response, user: None)

        client = TestClient(server.app)
        response = client.post(
            "/api/auth/login",
            json={"email": "prof.cs@example.com", "password": "demo-password"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["user"]["email"] == "prof.cs@example.com"

    def test_password_policy_still_runs_where_passwords_are_set(self) -> None:
        """Setting a password remains subject to the strength policy."""
        original = settings.DEBUG_MODE
        settings.DEBUG_MODE = False
        try:
            try:
                server._validate_password_input("demo-password")
            except Exception as exc:  # HTTPException carries status_code/detail
                assert getattr(exc, "status_code", None) == 400
                assert "uppercase" in str(getattr(exc, "detail", "")).lower()
            else:  # pragma: no cover - guards against policy silently vanishing
                raise AssertionError("password policy no longer rejects weak input")
        finally:
            settings.DEBUG_MODE = original
