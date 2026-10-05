"""Regression tests for session-cookie verification in the auth middleware.

``_has_valid_session_cookie`` runs on every request. If it raises rather than
returning ``False``, the exception escapes the auth check and surfaces as a 500
on *all* endpoints -- previously the whole application returned
"Something went wrong on our side" for every call, including AI detection.

The specific trap: ``settings.AUTH_JWT_SECRET`` is a ``pydantic.SecretStr`` and is
truthy, while ``settings.auth_jwt_secret`` is a plain ``str`` accessor. Probing the
``SecretStr`` attribute first makes an ``or`` fallback short-circuit and hands jose
a wrapper, which raises ``JWKError``. These tests pin the correct ordering and the
fail-closed behaviour that keeps a bad key from becoming a 500.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from jose import jwt

from src.backend.api.middleware.auth import AuthMiddleware
from src.backend.api.server import AUTH_COOKIE_NAME
from src.backend.config.settings import settings

FUTURE_EXP = 9999999999


def _request(cookies: dict[str, str]) -> SimpleNamespace:
    """Build a minimal request stub exposing only ``.cookies``."""
    return SimpleNamespace(cookies=cookies)


def _token(secret: str, **claims: object) -> str:
    """Mint an HS256 token with the given secret."""
    return jwt.encode(claims, secret, algorithm="HS256")


def test_valid_session_cookie_is_accepted() -> None:
    """A correctly signed, unexpired token must authenticate the request."""
    token = _token(settings.auth_jwt_secret, sub="user-1", exp=FUTURE_EXP)

    assert AuthMiddleware._has_valid_session_cookie(
        None, _request({AUTH_COOKIE_NAME: token})
    )


def test_token_signed_with_wrong_key_is_rejected() -> None:
    """A forged signature must fail closed instead of raising a 500."""
    token = _token("not-the-real-secret", sub="user-1", exp=FUTURE_EXP)

    assert not AuthMiddleware._has_valid_session_cookie(
        None, _request({AUTH_COOKIE_NAME: token})
    )


def test_expired_token_is_rejected() -> None:
    """An expired token must not authenticate."""
    token = _token(settings.auth_jwt_secret, sub="user-1", exp=1)

    assert not AuthMiddleware._has_valid_session_cookie(
        None, _request({AUTH_COOKIE_NAME: token})
    )


def test_token_without_exp_is_rejected() -> None:
    """python-jose only checks ``exp`` when present, so a missing one must be refused."""
    token = _token(settings.auth_jwt_secret, sub="user-1")

    assert not AuthMiddleware._has_valid_session_cookie(
        None, _request({AUTH_COOKIE_NAME: token})
    )


def test_missing_cookie_is_rejected() -> None:
    """A request with no session cookie is simply unauthenticated."""
    assert not AuthMiddleware._has_valid_session_cookie(None, _request({}))


def test_garbage_cookie_is_rejected() -> None:
    """A malformed cookie must fail closed rather than propagate a decoding error."""
    assert not AuthMiddleware._has_valid_session_cookie(
        None, _request({AUTH_COOKIE_NAME: "not-a-jwt"})
    )


def test_secret_wrapper_is_unwrapped_before_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the raw ``SecretStr`` attribute may exist; it must still be unwrapped.

    Guards the ordering fix: if ``auth_jwt_secret`` is absent, the middleware has to
    fall back to ``AUTH_JWT_SECRET`` and call ``get_secret_value()`` instead of
    passing the ``SecretStr`` wrapper to jose.
    """
    raw = SimpleNamespace(
        AUTH_JWT_SECRET=SimpleNamespace(
            get_secret_value=lambda: settings.auth_jwt_secret
        )
    )
    monkeypatch.setattr("src.backend.api.middleware.auth.settings", raw, raising=False)
    token = _token(settings.auth_jwt_secret, sub="user-1", exp=FUTURE_EXP)

    assert AuthMiddleware._has_valid_session_cookie(
        None, _request({AUTH_COOKIE_NAME: token})
    )


def test_non_string_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wrongly typed setting must fail closed rather than raise inside jose."""
    monkeypatch.setattr(
        "src.backend.api.middleware.auth.settings",
        SimpleNamespace(auth_jwt_secret=object()),
        raising=False,
    )

    assert not AuthMiddleware._has_valid_session_cookie(
        None, _request({AUTH_COOKIE_NAME: "anything"})
    )
