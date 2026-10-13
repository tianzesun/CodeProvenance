"""Regression test: changing the default LLM provider must persist."""

import uuid

from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.config.database import SessionLocal
from src.backend.models.database import Tenant, User


def _admin_with_tenant(monkeypatch):
    """Create a tenant + admin user; fake auth to return them."""
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
    return tenant_id


class TestDefaultLlmProviderRoundTrip:
    """PATCH llm_provider then GET settings must reflect the change."""

    def test_default_provider_change_persists(self, monkeypatch):
        """Test that selecting Ollama as default survives save + reload."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from src.backend.api.server import AUTH_COOKIE_NAME
        from src.backend.config.settings import settings as app_settings

        _admin_with_tenant(monkeypatch)
        now = datetime.now(timezone.utc)
        cookies = {
            AUTH_COOKIE_NAME: jose_jwt.encode(
                {"sub": "admin-1", "exp": now + timedelta(minutes=30), "iat": now},
                app_settings.auth_jwt_secret or "unit-test-secret",
                algorithm="HS256",
            )
        }
        client = TestClient(server.app)
        response = client.patch(
            "/api/settings",
            json={"llm_provider": "ollama"},
            cookies=cookies,
        )
        assert response.status_code == 200, response.text
        fresh = client.get("/api/settings", cookies=cookies)
        assert fresh.status_code == 200, fresh.text
        assert fresh.json().get("llm_provider") == "ollama"
