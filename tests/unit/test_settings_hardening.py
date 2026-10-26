"""Workspace settings: validation, secrets and server-wide switches."""

import os

import pytest
from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.infrastructure import secret_box


def test_saved_settings_never_replace_server_keys_with_asterisks() -> None:
    """The start-up SecretStr default stringifies to '**********'."""
    overrides = server._workspace_setting_overrides(
        {**server.USER_EDITABLE_SETTINGS_DEFAULTS}
    )

    assert "**********" not in {str(value) for value in overrides.values()}


def test_a_workspace_cannot_switch_on_debug_mode() -> None:
    assert "DEBUG_MODE" not in server._workspace_setting_overrides({"debug_mode": True})


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


def test_one_workspaces_key_does_not_carry_over_to_the_next() -> None:
    from src.backend.config.settings import workspace_overrides

    server_value = server.settings.OPENAI_API_KEY
    with workspace_overrides(
        server._workspace_setting_overrides({"openai_api_key": "workspace-a-key"})
    ):
        assert server.settings.OPENAI_API_KEY == "workspace-a-key"
    with workspace_overrides(server._workspace_setting_overrides({})):  # workspace B
        assert server.settings.OPENAI_API_KEY == server_value


def test_embedding_client_receives_the_real_key_not_the_mask() -> None:
    from pydantic import SecretStr

    from src.backend.engines.similarity.embedding_similarity import (
        EmbeddingSimilarity,
    )

    engine = EmbeddingSimilarity(api_key=SecretStr("sk-real"))

    assert engine.api_key == "sk-real"


@pytest.fixture
def workspace(monkeypatch):
    """A real workspace row and an admin client for it; yields (client, stored())."""
    import uuid
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    from src.backend.config.database import SessionLocal
    from src.backend.config.settings import settings as app_settings
    from src.backend.models.database import Tenant

    created: list[str] = []

    def make(saved: dict):
        with SessionLocal() as db:
            tenant = Tenant(
                name="Settings test",
                api_key_hash=f"test-hash-{uuid.uuid4().hex}",
                settings=saved,
            )
            db.add(tenant)
            db.commit()
            tenant_id = str(tenant.id)
        created.append(tenant_id)
        admin = {"id": str(uuid.uuid4()), "role": "admin", "tenant_id": tenant_id}
        monkeypatch.setattr(
            server, "_authenticate_request", lambda *a, **k: dict(admin)
        )
        monkeypatch.setattr(
            server, "_require_current_user", lambda *a, **k: dict(admin)
        )
        monkeypatch.setattr(server, "_record_weight_audit", lambda *a, **k: None)
        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {"sub": admin["id"], "exp": now + timedelta(minutes=30), "iat": now},
            app_settings.auth_jwt_secret or "unit-test-secret",
            algorithm="HS256",
        )
        client = TestClient(server.app)
        client.cookies.set(server.AUTH_COOKIE_NAME, token)

        def stored() -> dict:
            with SessionLocal() as db:
                return dict(db.get(Tenant, tenant_id).settings or {})

        stored.tenant_id = tenant_id
        return client, stored

    yield make
    with SessionLocal() as db:
        db.query(Tenant).filter(Tenant.id.in_(created)).delete(
            synchronize_session=False
        )
        db.commit()


def test_a_saved_key_can_be_removed_and_blank_keeps_the_rest(workspace) -> None:
    client, stored = workspace(
        {
            "openai_api_key": "workspace-openai",
            "llm_api_keys": {"openai": "workspace-openai", "groq": "gk"},
            "email_password": "smtp-secret",
        }
    )

    response = client.patch(
        "/api/settings",
        json={
            "openai_api_key": None,
            "llm_api_keys": {"openai": None, "groq": ""},
            "email_password": "",
        },
    )

    assert response.status_code == 200, response.text
    saved = stored()
    assert "openai_api_key" not in saved
    assert set(saved["llm_api_keys"]) == {"groq"}
    opened = secret_box.open_record(saved, stored.tenant_id)
    assert opened["llm_api_keys"] == {"groq": "gk"}
    assert opened["email_password"] == "smtp-secret"


def test_weights_without_validation_evidence_are_not_saved(workspace) -> None:
    from src.backend.engines.scoring import fusion_engine

    shared_before = fusion_engine.CONFIG_PATH.read_bytes()
    client, stored = workspace({})

    response = client.patch(
        "/api/settings", json={"engine_weights": {"token": 5.0, "ast": 0.1}}
    )

    assert response.status_code == 200, response.text
    assert "engine_weights" in response.json()["ignored"]
    assert "engine_weights" not in stored()
    assert fusion_engine.CONFIG_PATH.read_bytes() == shared_before


def test_a_profile_save_stays_in_its_workspace(workspace) -> None:
    from src.backend.engines.scoring import fusion_engine

    shared_before = fusion_engine.CONFIG_PATH.read_bytes()
    client, stored = workspace({})

    response = client.patch(
        "/api/settings",
        json={"professor_profile": {"starter_code_handling": "include_starter_code"}},
    )

    assert response.status_code == 200, response.text
    assert stored()["professor_profile"]["starter_code_handling"] == (
        "include_starter_code"
    )
    assert "engine_weights" in stored()
    assert fusion_engine.CONFIG_PATH.read_bytes() == shared_before


def test_a_new_key_is_stored_sealed_and_used(workspace) -> None:
    from src.backend.config.settings import workspace_overrides

    client, stored = workspace({})

    response = client.patch("/api/settings", json={"openai_api_key": "sk-new"})

    assert response.status_code == 200, response.text
    saved = stored()
    assert "sk-new" not in str(saved)
    assert secret_box.is_sealed(saved["openai_api_key"])
    overrides = server._workspace_setting_overrides(saved, stored.tenant_id)
    with workspace_overrides(overrides):
        assert server.settings.OPENAI_API_KEY == "sk-new"
        assert server.settings.llm_api_key("openai") == "sk-new"


def test_without_an_encryption_key_new_credentials_are_refused(
    workspace, override_setting
) -> None:
    client, stored = workspace({"email_host": "smtp.example.edu"})
    override_setting("SETTINGS_ENCRYPTION_KEY", None)

    refused = client.patch("/api/settings", json={"sendgrid_api_key": "SG.x"})
    other = client.patch("/api/settings", json={"email_port": 2525})

    assert refused.status_code == 400
    assert "sendgrid_api_key" in refused.json()["detail"]["fields"]
    assert other.status_code == 200, other.text
    assert "sendgrid_api_key" not in stored()


def _sealed(value="sk-1", workspace_id="ws-a", field="openai_api_key"):
    return secret_box.seal(value, workspace_id=workspace_id, field=field)


def test_sealed_values_round_trip() -> None:
    assert secret_box.unseal(
        _sealed(), workspace_id="ws-a", field="openai_api_key"
    ) == ("sk-1")


def test_a_sealed_value_only_opens_in_its_own_workspace_and_field() -> None:
    sealed = _sealed()

    assert (
        secret_box.unseal(sealed, workspace_id="ws-b", field="openai_api_key") is None
    )
    assert (
        secret_box.unseal(sealed, workspace_id="ws-a", field="email_password") is None
    )


def test_legacy_plain_text_values_are_still_read_and_get_sealed() -> None:
    record = {"email_password": "plain", "llm_api_keys": {"groq": "gk"}}

    sealed = secret_box.seal_record(record, "ws-a")

    assert secret_box.is_sealed(sealed["email_password"])
    assert secret_box.is_sealed(sealed["llm_api_keys"]["groq"])
    assert secret_box.open_record(sealed, "ws-a") == record
    assert secret_box.open_record(record, "ws-a") == record


def test_key_rotation_keeps_old_values_readable(override_setting) -> None:
    from pydantic import SecretStr

    old_key = server.settings.SETTINGS_ENCRYPTION_KEY
    sealed_with_old = _sealed()
    override_setting("SETTINGS_ENCRYPTION_KEY", SecretStr("A" * 43 + "="))
    override_setting("SETTINGS_ENCRYPTION_KEY_PREVIOUS", old_key)

    assert (
        secret_box.unseal(sealed_with_old, workspace_id="ws-a", field="openai_api_key")
        == "sk-1"
    )
    resealed = secret_box.seal_record({"openai_api_key": sealed_with_old}, "ws-a")
    assert resealed["openai_api_key"] != sealed_with_old
    override_setting("SETTINGS_ENCRYPTION_KEY_PREVIOUS", None)
    assert secret_box.open_record(resealed, "ws-a") == {"openai_api_key": "sk-1"}


def test_retired_keys_in_an_old_record_are_never_sent_back(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "_load_tenant_settings_record",
        lambda tenant_id: {"gptzero_api_key": "gz-old", "default_threshold": 0.7},
    )

    payload = server._build_settings_payload("any")

    assert "gz-old" not in str(payload)
    assert payload["default_threshold"] == 0.7
