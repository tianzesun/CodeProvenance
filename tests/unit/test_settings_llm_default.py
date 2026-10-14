"""Regression tests: the default LLM provider must persist and report drops."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from src.backend.api import server
from src.backend.api.server import AUTH_COOKIE_NAME
from src.backend.config.database import SessionLocal


def _delete_llm_default_test_rows() -> None:
    """Remove settings-test rows so reruns never pollute the workspace listing."""
    from src.backend.models.database import Tenant, User

    with SessionLocal() as db:
        db.query(User).filter(User.email.like("llm-default-%@%")).delete(
            synchronize_session=False
        )
        db.query(Tenant).filter(Tenant.name == "LLM Default Workspace").delete(
            synchronize_session=False
        )
        db.commit()


@pytest.fixture(autouse=True)
def _isolated_llm_default_rows():
    """Each test starts with no settings-test rows from earlier tests."""
    _delete_llm_default_test_rows()
    yield
    _delete_llm_default_test_rows()


from src.backend.config.settings import settings as app_settings
from src.backend.engines.scoring.fusion_engine import FusionEngine
from src.backend.models.database import Tenant, User


@pytest.fixture
def admin_client(monkeypatch):
    """Return a TestClient authed as an admin with a tenant.

    PATCH /api/settings always funnels through FusionEngine.update_config,
    which saves engine_weights.yaml on disk — neutralized here so tests never
    rewrite repo files.
    """
    monkeypatch.setattr(FusionEngine, "update_config", lambda config: None)
    email = f"llm-default-{uuid.uuid4().hex[:8]}@example.com"
    with SessionLocal() as db:
        tenant = Tenant(
            name="LLM Default Workspace",
            api_key_hash=f"test-hash-{uuid.uuid4().hex}",
        )
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email=email,
                full_name="Admin User",
                password_hash="already-hashed",
                role="admin",
                is_active=True,
            )
        )
        db.commit()
        tenant_id = tenant.id

    def fake_auth(request):
        return {"id": "admin-1", "role": "admin", "tenant_id": str(tenant_id)}

    monkeypatch.setattr(server, "_authenticate_request", fake_auth)
    now = datetime.now(timezone.utc)
    cookies = {
        AUTH_COOKIE_NAME: jose_jwt.encode(
            {"sub": "admin-1", "exp": now + timedelta(minutes=30), "iat": now},
            app_settings.auth_jwt_secret or "unit-test-secret",
            algorithm="HS256",
        )
    }
    return TestClient(server.app), cookies


class TestDefaultLlmProviderRoundTrip:
    """PATCH llm_provider then GET settings must reflect the change."""

    def test_default_provider_change_persists(self, admin_client):
        """Test that selecting Ollama as default survives save + reload."""
        client, cookies = admin_client
        response = client.patch(
            "/api/settings",
            json={"llm_provider": "ollama"},
            cookies=cookies,
        )
        assert response.status_code == 200, response.text
        fresh = client.get("/api/settings", cookies=cookies)
        assert fresh.status_code == 200, fresh.text
        assert fresh.json().get("llm_provider") == "ollama"

    def test_invalid_provider_is_reported_not_silently_dropped(self, admin_client):
        """Test that an unknown provider is named in the response."""
        client, cookies = admin_client
        response = client.patch(
            "/api/settings",
            json={"llm_provider": "not-a-vendor"},
            cookies=cookies,
        )
        assert response.status_code == 200, response.text
        ignored = response.json().get("ignored", {})
        assert "llm_provider" in ignored
        assert "not-a-vendor" in ignored["llm_provider"]

    def test_default_provider_survives_runtime_restart(self, admin_client):
        """Test that a restart restores the saved default on next request."""
        from src.backend.config.settings import settings as app_settings

        client, cookies = admin_client
        response = client.patch(
            "/api/settings",
            json={"llm_provider": "ollama"},
            cookies=cookies,
        )
        assert response.status_code == 200, response.text
        previous = app_settings.LLM_PROVIDER
        try:
            # Simulate a backend restart: the live object reverts to env
            # defaults while the tenant DB record keeps the saved value.
            object.__setattr__(app_settings, "LLM_PROVIDER", "openai")
            # The next authenticated request must re-apply the tenant record.
            fresh = client.get("/api/settings", cookies=cookies)
            assert fresh.status_code == 200, fresh.text
            assert fresh.json().get("llm_provider") == "ollama"
            assert app_settings.LLM_PROVIDER == "ollama"
        finally:
            object.__setattr__(app_settings, "LLM_PROVIDER", previous)
