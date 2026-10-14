"""Unit tests for the calibration endpoint (no real benchmark runs)."""

import pytest
from fastapi.testclient import TestClient

from src.backend.api import server
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


class TestTriggerCalibration:
    """POST /api/settings/calibrate access and result handling."""

    def test_non_admin_is_forbidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot trigger a benchmark run."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.post("/api/settings/calibrate", cookies=_cookie_jar())
        assert response.status_code == 403

    def test_success_returns_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a completed run passes metrics through untouched."""
        from src.backend.engines.scoring.fusion_engine import FusionEngine

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(
            FusionEngine,
            "run_calibration_benchmark",
            staticmethod(
                lambda: {"status": "completed", "f1": 0.9, "optimal_threshold": 0.62}
            ),
        )
        client = TestClient(server.app)
        response = client.post("/api/settings/calibrate", cookies=_cookie_jar())
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["results"]["f1"] == 0.9

    def test_failed_run_keeps_specific_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a failed run reports its error, not a generic message."""
        from src.backend.engines.scoring.fusion_engine import FusionEngine

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(
            FusionEngine,
            "run_calibration_benchmark",
            staticmethod(lambda: {"status": "failed", "error": "boom-metrics"}),
        )
        client = TestClient(server.app)
        response = client.post("/api/settings/calibrate", cookies=_cookie_jar())
        assert response.status_code == 500
        assert "boom-metrics" in response.json()["detail"]
