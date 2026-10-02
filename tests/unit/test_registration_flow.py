"""Self-service registration regression tests.

Registering must produce an account that cannot sign in until its inbox
redeems the emailed link. These tests pin down each half of that promise:

* the account is created inactive, as a professor, inside its own workspace,
  with the role never taken from the payload;
* the verification link is the only thing that activates it, and a lost or
  expired link is recovered by registering again — never by a silent
  activation;
* login explains the missing step instead of blaming the password, and the
  first successful sign-in consumes the token;
* the two endpoints are public, rate-limited, and non-enumerating for
  pending addresses.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.config.database import SessionLocal
from src.backend.config.settings import settings
from src.backend.infrastructure.email_service import EmailService
from src.backend.models.database import Tenant, User

STRONG_PASSWORD = "Register-Passw0rd"


def _unique_email() -> str:
    """Return an address no other test can collide with."""
    return f"signup-{uuid.uuid4().hex[:12]}@example.com"


def _cleanup(*emails: str) -> None:
    """Remove test accounts and their personal workspaces."""
    with SessionLocal() as db:
        for email in emails:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                continue
            tenant_id = user.tenant_id
            db.delete(user)
            if tenant_id:
                tenant = db.get(Tenant, tenant_id)
                if tenant is not None:
                    db.delete(tenant)
        db.commit()


def _register(client: TestClient, email: str, **overrides):
    """POST a registration payload with sensible test defaults."""
    payload = {
        "email": email,
        "full_name": "Signup Tester",
        "password": STRONG_PASSWORD,
    }
    payload.update(overrides)
    return client.post("/api/auth/register", json=payload)


def _token_from(url: str) -> str:
    """Extract the token from a captured verification URL."""
    return url.split("token=", 1)[1]


class TestRegistrationCreatesAnInactiveAccount:
    """A signup stores a locked account plus its workspace, nothing else."""

    def test_register_creates_an_inactive_professor_with_a_workspace(
        self, monkeypatch
    ) -> None:
        sent: list[tuple[str, str]] = []

        async def _capture(email: str, verify_url: str) -> bool:
            sent.append((email, verify_url))
            return True

        monkeypatch.setattr(EmailService, "send_verification_email", _capture)
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            response = _register(TestClient(server.app), email)

            assert response.status_code == 200, response.text
            assert "inbox" in response.json()["message"].lower()
            assert len(sent) == 1
            assert "/verify-email?token=" in sent[0][1]

            with SessionLocal() as db:
                user = db.query(User).filter(User.email == email).first()
                assert user is not None
                assert user.is_active is False
                assert user.role == "professor"
                assert user.tenant_id is not None
                assert user.password_hash != STRONG_PASSWORD
                assert user.verify_token == _token_from(sent[0][1])
                assert user.verify_token_expires is not None
        finally:
            _cleanup(email)

    def test_register_never_takes_a_role_from_the_payload(self, monkeypatch) -> None:
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            response = _register(
                TestClient(server.app), email, role="admin", tenant_id="somewhere"
            )

            assert response.status_code == 200, response.text
            with SessionLocal() as db:
                user = db.query(User).filter(User.email == email).first()
                assert user is not None
                assert user.role == "professor"
        finally:
            _cleanup(email)

    def test_register_rejects_a_malformed_email(self, monkeypatch) -> None:
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})

        response = _register(TestClient(server.app), "not-an-email")

        assert response.status_code == 400, response.text

    def test_register_rejects_a_weak_password(self, monkeypatch) -> None:
        # Force the policy active so the test holds even when DEBUG_MODE
        # would otherwise skip strength checks.
        monkeypatch.setattr(settings, "DEBUG_MODE", False)
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            response = _register(TestClient(server.app), email, password="too-short")

            assert response.status_code == 400, response.text
            assert "12 characters" in response.json()["detail"]
            with SessionLocal() as db:
                assert db.query(User).filter(User.email == email).first() is None
        finally:
            _cleanup(email)


class TestRegistrationRecoveryPaths:
    """Conflicts for active accounts; fresh links for pending ones."""

    def test_active_account_email_answers_conflict(self, monkeypatch) -> None:
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            with SessionLocal() as db:
                # Unique per test: api_key_hash is a UNIQUE column, so a
                # leftover row from a killed run must never collide with the
                # next test's tenant.
                tenant = Tenant(
                    name=f"{email} Workspace",
                    api_key_hash=f"test-hash-{uuid.uuid4().hex}",
                )
                db.add(tenant)
                db.flush()
                db.add(
                    User(
                        tenant_id=tenant.id,
                        email=email,
                        full_name="Existing User",
                        password_hash="already-hashed",
                        role="professor",
                        is_active=True,
                    )
                )
                db.commit()

            response = _register(TestClient(server.app), email)

            assert response.status_code == 409, response.text
            assert "sign in" in response.json()["detail"].lower()
        finally:
            _cleanup(email)

    def test_pending_account_gets_a_fresh_link_not_a_conflict(
        self, monkeypatch
    ) -> None:
        sent: list[str] = []

        async def _capture(email: str, verify_url: str) -> bool:
            sent.append(verify_url)
            return True

        monkeypatch.setattr(EmailService, "send_verification_email", _capture)
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            first = _register(TestClient(server.app), email)
            assert first.status_code == 200, first.text
            # A lost email is recovered by registering again — once the
            # send cooldown has elapsed, which the test simulates.
            server._REGISTER_RATE_LIMIT.clear()
            second = _register(TestClient(server.app), email)

            assert second.status_code == 200, second.text
            assert len(sent) == 2
            assert _token_from(sent[0]) != _token_from(sent[1]), "token must rotate"
            with SessionLocal() as db:
                users = db.query(User).filter(User.email == email).all()
                assert len(users) == 1, "a retry must not fork the account"
        finally:
            _cleanup(email)

    def test_cooldown_suppresses_duplicate_sends(self, monkeypatch) -> None:
        sent: list[str] = []

        async def _capture(email: str, verify_url: str) -> bool:
            sent.append(verify_url)
            return True

        monkeypatch.setattr(EmailService, "send_verification_email", _capture)
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            client = TestClient(server.app)
            first = _register(client, email)
            second = _register(client, email)

            assert first.status_code == 200
            assert second.status_code == 200, "cooldown answer matches a fresh signup"
            assert len(sent) == 1, "the cooldown must swallow the second send"
        finally:
            _cleanup(email)


class TestVerificationGate:
    """The emailed link is the only thing that can activate an account."""

    def test_login_before_verification_explains_the_missing_step(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            assert _register(TestClient(server.app), email).status_code == 200

            response = TestClient(server.app).post(
                "/api/auth/login",
                json={"email": email, "password": STRONG_PASSWORD},
            )

            assert response.status_code == 403, response.text
            assert "verified" in response.json()["detail"].lower()
        finally:
            _cleanup(email)

    def test_verification_activates_then_login_works_and_consumes_token(
        self, monkeypatch
    ) -> None:
        sent: list[str] = []

        async def _capture(email: str, verify_url: str) -> bool:
            sent.append(verify_url)
            return True

        monkeypatch.setattr(EmailService, "send_verification_email", _capture)
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            client = TestClient(server.app)
            assert _register(client, email).status_code == 200

            verify = client.post(
                "/api/auth/verify-email", json={"token": _token_from(sent[0])}
            )
            assert verify.status_code == 200, verify.text

            login = client.post(
                "/api/auth/login", json={"email": email, "password": STRONG_PASSWORD}
            )
            assert login.status_code == 200, login.text

            with SessionLocal() as db:
                user = db.query(User).filter(User.email == email).first()
                assert user is not None and user.is_active is True
                assert user.verify_token is None, "sign-in must consume the token"
                assert user.verify_token_expires is None
        finally:
            _cleanup(email)

    def test_verifying_twice_stays_successful_for_mail_prefetchers(
        self, monkeypatch
    ) -> None:
        sent: list[str] = []

        async def _capture(email: str, verify_url: str) -> bool:
            sent.append(verify_url)
            return True

        monkeypatch.setattr(EmailService, "send_verification_email", _capture)
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        email = _unique_email()

        try:
            client = TestClient(server.app)
            assert _register(client, email).status_code == 200
            token = _token_from(sent[0])

            first = client.post("/api/auth/verify-email", json={"token": token})
            second = client.post("/api/auth/verify-email", json={"token": token})

            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
        finally:
            _cleanup(email)

    def test_unknown_and_expired_tokens_are_rejected(self, monkeypatch) -> None:
        monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
        client = TestClient(server.app)
        email = _unique_email()

        try:
            unknown = client.post("/api/auth/verify-email", json={"token": "bogus"})
            assert unknown.status_code == 400, unknown.text

            assert _register(client, email).status_code == 200
            with SessionLocal() as db:
                user = db.query(User).filter(User.email == email).first()
                assert user is not None
                # Read before commit: expiry is a mutable column, and the
                # session expires attributes on commit.
                token = user.verify_token
                user.verify_token_expires = datetime.now(timezone.utc) - timedelta(
                    minutes=1
                )
                db.add(user)
                db.commit()

            expired = client.post("/api/auth/verify-email", json={"token": token})
            assert expired.status_code == 400, expired.text

            # Still inactive and still locked out of login.
            login = client.post(
                "/api/auth/login", json={"email": email, "password": STRONG_PASSWORD}
            )
            assert login.status_code in (403, 429), login.text
        finally:
            _cleanup(email)


class TestRegistrationSurface:
    """Both endpoints answer before any session exists."""

    def test_registration_endpoints_are_public(self) -> None:
        client = TestClient(server.app)

        register = client.post("/api/auth/register", json={})
        verify = client.post("/api/auth/verify-email", json={})

        assert register.status_code == 400, register.text
        assert verify.status_code == 400, verify.text
        assert "credential" not in register.text.lower()

    def test_verification_requires_a_token(self) -> None:
        response = TestClient(server.app).post("/api/auth/verify-email", json={})

        assert response.status_code == 400, response.text
