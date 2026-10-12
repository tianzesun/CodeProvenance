"""Unit tests for weight-governance evidence endpoints (no real config writes)."""

import copy

import pytest
from fastapi.testclient import TestClient

from src.backend.config.settings import settings as app_settings


def _cookie_jar() -> dict[str, str]:
    """Return a valid session cookie accepted by the auth middleware."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    from src.backend.api.server import AUTH_COOKIE_NAME

    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": "admin-1", "exp": now + timedelta(minutes=30), "iat": now},
        app_settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    return {AUTH_COOKIE_NAME: token}


def _fake_admin(*args, **kwargs):
    return {"id": "admin-1", "role": "admin"}


def _fake_professor(*args, **kwargs):
    return {"id": "prof-1", "role": "professor"}


def _stored_config() -> dict:
    """Return a config with a pending, unevidenced weight change."""
    return {
        "weights": {"ast": 0.5, "token": 0.5},
        "advanced": {"weights_need_validation": True},
    }


def _evidence_payload() -> dict:
    """Return a complete validation-evidence payload."""
    return {
        "validation_run_id": "val-2026-01-01",
        "benchmark_dataset_id": "pan-validation",
        "metric_snapshot": "F1 0.91, AUC-PR 0.93",
    }


class TestAttachWeightGovernanceEvidence:
    """POST /api/settings/weight-governance-evidence behavior."""

    def test_records_evidence_and_clears_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that complete evidence clears the pending-validation flag."""
        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(
            fusion_engine, "load_engine_config", lambda: _stored_config()
        )
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence",
            json=_evidence_payload(),
            cookies=_cookie_jar(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["cleared"] is True
        advanced = saved["advanced"]
        assert "weights_need_validation" not in advanced
        assert (
            advanced["weight_governance_evidence"]["validation_run_id"]
            == "val-2026-01-01"
        )

    def test_missing_fields_are_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that incomplete evidence returns 400 naming the gaps."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence",
            json={"validation_run_id": "val-1"},
            cookies=_cookie_jar(),
        )
        assert response.status_code == 400
        assert "benchmark_dataset_id" in response.json()["detail"]
        assert "metric_snapshot" in response.json()["detail"]

    def test_non_admin_is_forbidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot record validation evidence."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence",
            json=_evidence_payload(),
            cookies=_cookie_jar(),
        )
        assert response.status_code == 403


class TestValidationGovernanceBlock:
    """GET /api/settings/validation exposes governance state for the UI."""

    def test_response_includes_governance_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the validation payload carries the governance block."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        client = TestClient(server.app)
        response = client.get("/api/settings/validation", cookies=_cookie_jar())
        assert response.status_code == 200
        block = response.json()["weight_governance"]
        assert set(block) == {
            "needs_validation",
            "changed_engines",
            "evidence",
            "warnings",
        }
