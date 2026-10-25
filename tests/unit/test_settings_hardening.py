"""Workspace settings: validation, secrets and server-wide switches."""

import os

import pytest
from fastapi.testclient import TestClient

from src.backend.api import server


def test_saved_settings_do_not_overwrite_server_keys_with_asterisks(
    monkeypatch,
) -> None:
    """The start-up SecretStr default stringifies to '**********'."""
    monkeypatch.setenv("OPENAI_API_KEY", "server-configured-key")

    server._apply_runtime_settings_from_record({})

    assert os.environ["OPENAI_API_KEY"] == "server-configured-key"


def test_a_workspaces_own_key_is_still_applied(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "server-configured-key")

    server._apply_runtime_settings_from_record({"openai_api_key": "workspace-key"})

    assert os.environ["OPENAI_API_KEY"] == "workspace-key"


def test_a_workspace_cannot_switch_on_debug_mode(monkeypatch) -> None:
    before = server.settings.DEBUG_MODE

    server._apply_runtime_settings_from_record({"debug_mode": not before})

    assert server.settings.DEBUG_MODE == before


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("default_threshold", -5),
        ("default_threshold", 1.5),
        ("max_files_per_job", 0),
        ("max_file_size_mb", "big"),
        ("email_port", "abc"),
        ("embedding_server_port", 70000),
        ("embedding_device", "gpu"),
        ("email_backend", "pigeon"),
        ("webhook_url", "ftp://example.com"),
        ("email_from", "not-an-email"),
        ("email_use_tls", "yes"),
        ("batch_size", 2.5),
    ],
)
def test_invalid_settings_are_rejected(key, value) -> None:
    with pytest.raises(ValueError):
        server.SETTINGS_VALIDATORS[key](value)


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("default_threshold", "0.7", 0.7),
        ("max_files_per_job", "500", 500),
        ("embedding_device", "CUDA:1", "cuda:1"),
        ("email_backend", "SMTP", "smtp"),
        ("webhook_url", "https://hooks.example.com/x/", "https://hooks.example.com/x"),
        ("webhook_url", "", ""),
    ],
)
def test_valid_settings_are_normalised(key, value, expected) -> None:
    assert server.SETTINGS_VALIDATORS[key](value) == expected


def test_patch_reports_every_invalid_field(monkeypatch) -> None:
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    from src.backend.config.settings import settings as app_settings

    admin = {
        "id": "00000000-0000-4000-8000-0000000000aa",
        "role": "admin",
        "tenant_id": "00000000-0000-4000-8000-0000000000bb",
    }
    monkeypatch.setattr(server, "_authenticate_request", lambda *a, **k: dict(admin))
    monkeypatch.setattr(server, "_require_current_user", lambda *a, **k: dict(admin))

    # Validation runs before the tenant is loaded; this tenant does not exist, so a
    # request that got past it would 404 rather than store anything.
    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": admin["id"], "exp": now + timedelta(minutes=30), "iat": now},
        app_settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    client = TestClient(server.app)
    client.cookies.set(server.AUTH_COOKIE_NAME, token)
    response = client.patch(
        "/api/settings",
        json={"default_threshold": -5, "max_files_per_job": 0, "debug_mode": True},
    )

    assert response.status_code == 400
    fields = response.json()["detail"]["fields"]
    assert set(fields) == {"default_threshold", "max_files_per_job", "debug_mode"}


@pytest.mark.parametrize(
    ("volume", "limit"),
    [("top_10", 10), ("top_25", 25), ("top_50", 50), ("all", None), ("bogus", 25)],
)
def test_result_volume_sets_the_results_page_limit(volume, limit) -> None:
    assert server._profile_result_limit({"result_volume": volume}) == limit
