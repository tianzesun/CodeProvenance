"""Tests for login brute-force rate limiting."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from src.backend.api.server import (
    LOGIN_ATTEMPTS,
    LOGIN_ATTEMPTS_LOCK,
    MAX_LOGIN_ATTEMPTS,
    _check_login_rate_limit,
    _clear_login_attempts,
    _record_login_failure,
)


def test_login_succeeds_below_threshold() -> None:
    """A few failed attempts should not lock the account."""
    _clear_login_attempts("prof@example.com")
    _record_login_failure("prof@example.com")
    _check_login_rate_limit("prof@example.com")  # should not raise


def test_login_rejected_at_threshold() -> None:
    """The account is locked once attempts reach the threshold."""
    email = "locked@example.com"
    _clear_login_attempts(email)
    for _ in range(MAX_LOGIN_ATTEMPTS):
        _record_login_failure(email)
    with pytest.raises(HTTPException) as exc_info:
        _check_login_rate_limit(email)
    assert exc_info.value.status_code == 429


def test_clear_login_attempts_unlocks_account() -> None:
    """A successful login clears the failure counter."""
    email = "retry@example.com"
    _clear_login_attempts(email)
    for _ in range(MAX_LOGIN_ATTEMPTS):
        _record_login_failure(email)
    _clear_login_attempts(email)
    _check_login_rate_limit(email)  # should not raise


def test_expired_attempts_do_not_count() -> None:
    """Failures older than the window are ignored."""
    email = "expired@example.com"
    # Simulate an expired attempt: older than the window.
    with LOGIN_ATTEMPTS_LOCK:
        LOGIN_ATTEMPTS[email] = [datetime.now(timezone.utc) - timedelta(seconds=1000)]
    _check_login_rate_limit(email)  # should not raise
