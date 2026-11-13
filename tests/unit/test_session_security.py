"""Password hashing and session lifetime rules (no database needed)."""

import contextlib
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from passlib.context import CryptContext

from src.backend.api import server
from src.backend.config.settings import settings
from src.backend.infrastructure import security

PASSWORD = "Session-Passw0rd"


def test_new_hashes_are_argon2id() -> None:
    assert security.hash_password(PASSWORD).startswith("$argon2id$")


def test_a_legacy_pbkdf2_hash_still_works_and_is_upgraded() -> None:
    legacy = CryptContext(schemes=["pbkdf2_sha256"]).hash(PASSWORD)

    ok, upgraded = security.verify_and_upgrade_password(PASSWORD, legacy)
    assert ok and upgraded.startswith("$argon2id$")
    assert security.verify_password(PASSWORD, upgraded)
    assert security.verify_and_upgrade_password("wrong", legacy) == (False, None)
    current = security.hash_password(PASSWORD)
    assert security.verify_and_upgrade_password(PASSWORD, current) == (True, None)


def _user(password_hash: str):
    return types.SimpleNamespace(
        id=str(uuid.uuid4()),
        email="s@example.edu",
        full_name="Session Tester",
        role="professor",
        tenant_id=None,
        tenant=None,
        organization_id=None,
        is_active=True,
        last_login_at=None,
        created_at=None,
        password_hash=password_hash,
    )


def _claims(token: str) -> dict:
    return jose_jwt.decode(token, settings.auth_jwt_secret or "", algorithms=["HS256"])


def test_tokens_carry_the_sign_in_time_and_a_password_fingerprint() -> None:
    user = _user("hash-1")
    claims = _claims(server._create_access_token(user))

    assert claims["pwd"] == server._password_fingerprint("hash-1")
    assert claims["pwd"] != server._password_fingerprint("hash-2")
    assert abs(claims["auth_time"] - datetime.now(timezone.utc).timestamp()) < 5


def test_a_token_never_outlives_the_maximum_session() -> None:
    signed_in = datetime.now(timezone.utc) - timedelta(
        hours=settings.AUTH_SESSION_MAX_HOURS - 1
    )
    claims = _claims(server._create_access_token(_user("h"), signed_in))

    cap = signed_in + timedelta(hours=settings.AUTH_SESSION_MAX_HOURS)
    assert claims["exp"] <= int(cap.timestamp()) + 1
    assert claims["auth_time"] == int(signed_in.timestamp())


def _fake_session_db(user):
    class _Db:
        def scalar(self, statement):
            return user

    @contextlib.contextmanager
    def _session():
        yield _Db()

    return _session


def _request_with(token: str):
    return types.SimpleNamespace(cookies={server.AUTH_COOKIE_NAME: token}, headers={})


def test_a_session_from_before_a_password_change_ends(monkeypatch) -> None:
    user = _user("old-hash")
    token = server._create_access_token(user)
    monkeypatch.setattr(server, "SessionLocal", _fake_session_db(user))

    assert server._authenticate_request(_request_with(token))["id"] == user.id

    user.password_hash = "new-hash"  # a reset or password change
    with pytest.raises(HTTPException) as exc:
        server._authenticate_request(_request_with(token))
    assert exc.value.status_code == 401
    assert "password was changed" in exc.value.detail


def _refresh_with(monkeypatch, user, token: str):
    monkeypatch.setattr(server, "SessionLocal", _fake_session_db(user))
    monkeypatch.setattr(server, "_get_user_by_id", lambda user_id: user)
    client = TestClient(server.app)
    client.cookies.set(server.AUTH_COOKIE_NAME, token)
    return client.post("/api/auth/refresh")


def test_refresh_keeps_the_sign_in_time(monkeypatch) -> None:
    user = _user("h")
    signed_in = datetime.now(timezone.utc) - timedelta(hours=2)

    response = _refresh_with(
        monkeypatch, user, server._create_access_token(user, signed_in)
    )

    assert response.status_code == 200, response.text
    renewed = _claims(response.cookies[server.AUTH_COOKIE_NAME])
    assert renewed["auth_time"] == int(signed_in.timestamp())


def test_refresh_stops_at_the_maximum_session(monkeypatch) -> None:
    user = _user("h")
    now = datetime.now(timezone.utc)
    stale = jose_jwt.encode(
        {
            "sub": user.id,
            "exp": now + timedelta(minutes=30),
            "iat": now,
            "auth_time": int(
                (now - timedelta(hours=settings.AUTH_SESSION_MAX_HOURS)).timestamp()
            ),
            "pwd": server._password_fingerprint("h"),
        },
        settings.auth_jwt_secret or "",
        algorithm="HS256",
    )

    response = _refresh_with(monkeypatch, user, stale)

    assert response.status_code == 401
    assert "maximum length" in response.text


def test_refresh_does_not_renew_tokens_from_before_this_change(monkeypatch) -> None:
    user = _user("h")
    now = datetime.now(timezone.utc)
    legacy = jose_jwt.encode(
        {"sub": user.id, "exp": now + timedelta(minutes=30), "iat": now},
        settings.auth_jwt_secret or "",
        algorithm="HS256",
    )

    response = _refresh_with(monkeypatch, user, legacy)

    assert response.status_code == 401
    assert "sign in again" in response.text.lower()
