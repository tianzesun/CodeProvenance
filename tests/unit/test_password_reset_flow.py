"""Password-reset regression tests.

The reset chain has to survive the full loop a real user walks: ask for a
link with the address typed in any case, redeem the token once, then sign
in with the new credential while the old one stops working. These tests
pin down the pieces that loop depends on:

* ``forgot-password`` normalizes the address exactly like every other
  auth path stores it — otherwise a mixed-case request claims success
  while no email is ever sent;
* the token is single-use and validated before the password policy, so a
  rejected weak password never burns the link;
* responses stay generic (no account enumeration) and rate-limited.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.api.routes import auth as auth_routes
from src.backend.config.database import SessionLocal
from src.backend.config.settings import settings
from src.backend.infrastructure.email_service import EmailService
from src.backend.infrastructure.security import hash_password
from src.backend.models.database import Tenant, User

ORIGINAL_PASSWORD = "Original-Passw0rd1"
NEW_PASSWORD = "Brand-New-Passw0rd2"


def _unique_email() -> str:
    """Return an address no other test can collide with."""
    return f"reset-{uuid.uuid4().hex[:12]}@example.com"


def _create_active_user(email: str, password: str = ORIGINAL_PASSWORD) -> str:
    """Insert an active account and return its tenant id for cleanup."""
    with SessionLocal() as db:
        # Unique per test: api_key_hash is a UNIQUE column, so a leftover row
        # from a killed run must never collide with the next test's tenant.
        tenant = Tenant(
            name=f"{email} Workspace", api_key_hash=f"test-hash-{uuid.uuid4().hex}"
        )
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email=email,
                full_name="Reset Tester",
                password_hash=hash_password(password),
                role="professor",
                is_active=True,
            )
        )
        db.commit()
        return tenant.id


def _cleanup(email: str) -> None:
    """Remove the test account and its personal workspace."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            return
        tenant_id = user.tenant_id
        db.delete(user)
        if tenant_id:
            tenant = db.get(Tenant, tenant_id)
            if tenant is not None:
                db.delete(tenant)
        db.commit()


def _extract_token(sent: list[tuple[str, str]]) -> str:
    """Pull the reset token out of the captured reset URL."""
    return sent[0][1].split("token=", 1)[1]


class TestForgotPassword:
    """The reset request must reach the inbox no matter how it is typed."""

    def test_mixed_case_email_still_sends_the_link(self, monkeypatch) -> None:
        sent: list[tuple[str, str]] = []

        async def _capture(email: str, reset_url: str) -> bool:
            sent.append((email, reset_url))
            return True

        monkeypatch.setattr(EmailService, "send_password_reset_email", _capture)
        monkeypatch.setattr(auth_routes, "_forgot_password_rate_limit", {})
        email = _unique_email()
        mixed_case = email.upper()  # stored lowercase, requested uppercase

        try:
            _create_active_user(email)
            response = TestClient(server.app).post(
                "/api/auth/forgot-password", json={"email": mixed_case}
            )

            assert response.status_code == 200, response.text
            assert "if an account" in response.json()["message"].lower()
            assert len(sent) == 1, "mixed-case request must still send the email"
            assert sent[0][0] == email, "email must be delivered normalized"
            assert "/reset-password?token=" in sent[0][1]

            with SessionLocal() as db:
                user = db.query(User).filter(User.email == email).first()
                assert user is not None and user.reset_token is not None
                assert user.reset_token_expires is not None
        finally:
            _cleanup(email)

    def test_unknown_email_answers_the_same_generic_message(self, monkeypatch) -> None:
        sent: list[str] = []

        async def _capture(email: str, reset_url: str) -> bool:
            sent.append(email)
            return True

        monkeypatch.setattr(EmailService, "send_password_reset_email", _capture)
        monkeypatch.setattr(auth_routes, "_forgot_password_rate_limit", {})

        response = TestClient(server.app).post(
            "/api/auth/forgot-password", json={"email": _unique_email()}
        )

        assert response.status_code == 200, response.text
        assert "if an account" in response.json()["message"].lower()
        assert sent == [], "no email may go to an unknown address"

    def test_cooldown_suppresses_duplicate_sends(self, monkeypatch) -> None:
        sent: list[str] = []

        async def _capture(email: str, reset_url: str) -> bool:
            sent.append(email)
            return True

        monkeypatch.setattr(EmailService, "send_password_reset_email", _capture)
        monkeypatch.setattr(auth_routes, "_forgot_password_rate_limit", {})
        email = _unique_email()

        try:
            _create_active_user(email)
            client = TestClient(server.app)
            client.post("/api/auth/forgot-password", json={"email": email})
            second = client.post("/api/auth/forgot-password", json={"email": email})

            assert second.status_code == 200
            assert len(sent) == 1, "the cooldown must swallow the second send"
        finally:
            _cleanup(email)


class TestResetPassword:
    """Redeeming the token replaces the credential exactly once."""

    def test_reset_rotates_the_password_and_kills_the_old_one(
        self, monkeypatch
    ) -> None:
        sent: list[tuple[str, str]] = []

        async def _capture(email: str, reset_url: str) -> bool:
            sent.append((email, reset_url))
            return True

        monkeypatch.setattr(EmailService, "send_password_reset_email", _capture)
        monkeypatch.setattr(auth_routes, "_forgot_password_rate_limit", {})
        email = _unique_email()

        try:
            _create_active_user(email)
            client = TestClient(server.app)
            assert (
                client.post(
                    "/api/auth/forgot-password", json={"email": email}
                ).status_code
                == 200
            )
            token = _extract_token(sent)

            reset = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": NEW_PASSWORD},
            )
            assert reset.status_code == 200, reset.text

            old = client.post(
                "/api/auth/login", json={"email": email, "password": ORIGINAL_PASSWORD}
            )
            new = client.post(
                "/api/auth/login", json={"email": email, "password": NEW_PASSWORD}
            )
            assert old.status_code == 401, "old credential must stop working"
            assert new.status_code == 200, new.text
        finally:
            _cleanup(email)

    def test_token_is_single_use(self, monkeypatch) -> None:
        sent: list[tuple[str, str]] = []

        async def _capture(email: str, reset_url: str) -> bool:
            sent.append((email, reset_url))
            return True

        monkeypatch.setattr(EmailService, "send_password_reset_email", _capture)
        monkeypatch.setattr(auth_routes, "_forgot_password_rate_limit", {})
        email = _unique_email()

        try:
            _create_active_user(email)
            client = TestClient(server.app)
            client.post("/api/auth/forgot-password", json={"email": email})
            token = _extract_token(sent)

            first = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": NEW_PASSWORD},
            )
            second = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "Another-Passw0rd3"},
            )

            assert first.status_code == 200, first.text
            assert second.status_code == 400, "a redeemed token must not replay"
        finally:
            _cleanup(email)

    def test_unknown_and_expired_tokens_are_rejected(self, monkeypatch) -> None:
        monkeypatch.setattr(auth_routes, "_forgot_password_rate_limit", {})
        client = TestClient(server.app)
        email = _unique_email()

        try:
            unknown = client.post(
                "/api/auth/reset-password",
                json={"token": "bogus", "new_password": NEW_PASSWORD},
            )
            assert unknown.status_code == 400, unknown.text

            _create_active_user(email)
            client.post("/api/auth/forgot-password", json={"email": email})
            with SessionLocal() as db:
                user = db.query(User).filter(User.email == email).first()
                assert user is not None
                # Read before commit: the session expires attributes on commit.
                token = user.reset_token
                user.reset_token_expires = datetime.now(timezone.utc) - timedelta(
                    minutes=1
                )
                db.add(user)
                db.commit()

            expired = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": NEW_PASSWORD},
            )
            assert expired.status_code == 400, expired.text

            # Password untouched: the original credential still signs in.
            login = client.post(
                "/api/auth/login",
                json={"email": email, "password": ORIGINAL_PASSWORD},
            )
            assert login.status_code in (200, 429), login.text
        finally:
            _cleanup(email)

    def test_weak_new_password_is_rejected_without_burning_the_token(
        self, monkeypatch
    ) -> None:
        # Force the policy active so the test holds even when DEBUG_MODE
        # would otherwise skip strength checks.
        monkeypatch.setattr(settings, "DEBUG_MODE", False)
        monkeypatch.setattr(auth_routes, "_forgot_password_rate_limit", {})
        sent: list[tuple[str, str]] = []

        async def _capture(email: str, reset_url: str) -> bool:
            sent.append((email, reset_url))
            return True

        monkeypatch.setattr(EmailService, "send_password_reset_email", _capture)
        email = _unique_email()

        try:
            _create_active_user(email)
            client = TestClient(server.app)
            client.post("/api/auth/forgot-password", json={"email": email})
            token = _extract_token(sent)

            weak = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "short"},
            )
            assert weak.status_code == 400, weak.text

            # The rejected attempt must not consume the link: the same token
            # still works with a compliant password.
            strong = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": NEW_PASSWORD},
            )
            assert strong.status_code == 200, strong.text
        finally:
            _cleanup(email)
