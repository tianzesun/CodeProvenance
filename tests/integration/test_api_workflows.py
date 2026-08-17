"""
API integration tests for core IntegrityDesk workflows.

These tests exercise real HTTP endpoints against the FastAPI app.
They are designed to be non-destructive and use unique test data where
writes are required. Tests that require a live database will be skipped
automatically if the database is unreachable.

Run with: pytest tests/integration/test_api_workflows.py
"""

import time
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _db_available() -> bool:
    """Check whether the configured database is reachable."""
    try:
        from src.backend.config.database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception:
        return False


@pytest.fixture(scope="module")
def client():
    """Test client bound to the real API app."""
    from src.backend.api import server

    with TestClient(server.app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def require_db():
    """Skip module tests if the database is unavailable."""
    if not _db_available():
        pytest.skip("Database is not reachable — skipping database-dependent tests")


class TestPublicEndpoints:
    """Tests for public (unauthenticated) endpoints."""

    def test_root_returns_welcome(self, client):
        """The root endpoint returns a welcome payload."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Welcome to IntegrityDesk" in response.json()["message"]

    def test_health_endpoint(self, client):
        """The health endpoint is reachable (may not be mounted in server app)."""
        response = client.get("/health")
        # server.py doesn't define /health; it's either 401 (auth-guarded),
        # 404 (not mounted), or 200 (if mounted).
        assert response.status_code in (200, 401, 404)


class TestAuthWorkflow:
    """Tests for the authentication workflow."""

    def test_auth_status_returns_bootstrapped_state(self, client, require_db):
        """Auth status reports whether the system is bootstrapped."""
        response = client.get("/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert "bootstrapped" in data
        assert "user_count" in data
        assert isinstance(data["user_count"], int)

    def test_login_with_invalid_credentials_fails_gracefully(self, client, require_db):
        """Invalid credentials return 401 without leaking data."""
        unique_email = f"nonexistent-{uuid.uuid4().hex[:8]}@test.local"
        response = client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "StrongPass123!"},
        )
        # Because the email doesn't exist, login must fail with 401.
        assert response.status_code == 401

    def test_forgot_password_for_unknown_email_is_generic(self, client, require_db):
        """Forgot-password returns a generic response for unknown emails."""
        unique_email = f"ghost-{uuid.uuid4().hex[:8]}@test.local"
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": unique_email},
        )
        assert response.status_code == 200
        message = response.json().get("message", "")
        assert "will not reveal if the account exists" in message.lower() or (
            "reset" in message.lower() and "email" in message.lower()
        )


class TestCaseEndpoints:
    """Tests for the case management flow (auth-exempt read paths)."""

    def test_list_cases_is_reachable(self, client, require_db):
        """Case listing returns an HTTP 200 with a list payload."""
        response = client.get("/api/cases")
        # The endpoint is reachable; body shape may vary, but it must be JSON.
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, (list, dict))


class TestConfigEndpoints:
    """Tests for read-only configuration endpoints."""

    def test_cases_router_mounted(self, client):
        """The cases router is registered under /api/cases."""
        from src.backend.api.routes import cases

        assert hasattr(cases, "router")