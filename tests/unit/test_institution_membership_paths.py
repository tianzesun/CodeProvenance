"""New accounts join the institution's organization only on the agreed paths."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.config.database import SessionLocal
from src.backend.config.settings import settings
from src.backend.infrastructure.email_service import EmailService
from src.backend.models.database import Organization, Tenant, User

PASSWORD = "Register-Passw0rd"


class _FakeDb:
    """Just enough session for _institution_organization_id."""

    def __init__(self, ids):
        self.ids, self.added = list(ids), []

    def scalars(self, statement):
        return type("R", (), {"all": lambda _self: list(self.ids)[:2]})()

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            obj.id = obj.id or "new-org"


def test_the_one_organization_is_found_and_never_guessed() -> None:
    assert server._institution_organization_id(_FakeDb(["o1"])) == "o1"
    assert server._institution_organization_id(_FakeDb([])) is None
    assert server._institution_organization_id(_FakeDb(["o1", "o2"])) is None
    assert (
        server._institution_organization_id(_FakeDb(["o1", "o2"]), create=True) is None
    )


def test_bootstrap_creates_the_named_organization(monkeypatch) -> None:
    monkeypatch.setattr(settings, "INSTITUTION_NAME", "University of Toronto")
    db = _FakeDb([])

    assert server._institution_organization_id(db, create=True) == "new-org"
    assert [o.name for o in db.added] == ["University of Toronto"]


def test_admin_created_accounts_join_the_admins_organization(monkeypatch) -> None:
    monkeypatch.setattr(
        server, "_institution_organization_id", lambda db, create=False: "inst"
    )

    assert (
        server._member_organization_id(None, {"organization_id": "admins-org"})
        == "admins-org"
    )
    assert server._member_organization_id(None, {"organization_id": None}) == "inst"


def test_registration_joins_only_from_a_listed_domain(monkeypatch) -> None:
    monkeypatch.setattr(
        server, "_institution_organization_id", lambda db, create=False: "inst"
    )
    monkeypatch.setattr(settings, "INSTITUTION_EMAIL_DOMAINS", "utoronto.ca")

    assert server._registration_organization_id(None, "prof@UToronto.ca") == "inst"
    assert server._registration_organization_id(None, "someone@gmail.com") is None
    monkeypatch.setattr(settings, "INSTITUTION_EMAIL_DOMAINS", "")
    assert server._registration_organization_id(None, "prof@utoronto.ca") is None


# ── Through the endpoints (need the database; run in CI) ──


@pytest.fixture
def institution(monkeypatch):
    """A real organization row, pinned as the deployment's one organization."""
    org_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(Organization(id=org_id, name=f"Membership test {org_id}"))
        db.commit()
    monkeypatch.setattr(
        server, "_institution_organization_id", lambda db, create=False: org_id
    )
    monkeypatch.setattr(settings, "INSTITUTION_EMAIL_DOMAINS", "member.example.edu")
    monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})

    async def _no_email(email, url):
        return True

    monkeypatch.setattr(EmailService, "send_verification_email", _no_email)
    emails: list[str] = []
    yield org_id, emails
    with SessionLocal() as db:
        for email in emails:
            user = db.query(User).filter(User.email == email).first()
            if user is not None:
                tenant_id = user.tenant_id
                db.delete(user)
                if tenant_id and (tenant := db.get(Tenant, tenant_id)) is not None:
                    db.delete(tenant)
        db.commit()
        if (org := db.get(Organization, org_id)) is not None:
            db.delete(org)
        db.commit()


def _organization_of(email: str):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        return str(user.organization_id) if user and user.organization_id else None


def _register(email: str):
    return TestClient(server.app).post(
        "/api/auth/register",
        json={"email": email, "full_name": "Member Tester", "password": PASSWORD},
    )


def test_a_listed_domain_registration_joins_an_unlisted_one_waits(institution) -> None:
    org_id, emails = institution
    member = f"m-{uuid.uuid4().hex[:10]}@member.example.edu"
    outsider = f"o-{uuid.uuid4().hex[:10]}@elsewhere.example.com"
    emails += [member, outsider]

    assert _register(member).status_code in (200, 201)
    assert _register(outsider).status_code in (200, 201)

    assert _organization_of(member) == org_id
    assert _organization_of(outsider) is None


def test_a_pending_registration_joins_when_it_asks_again(
    institution, monkeypatch
) -> None:
    org_id, emails = institution
    email = f"p-{uuid.uuid4().hex[:10]}@member.example.edu"
    emails.append(email)
    monkeypatch.setattr(settings, "INSTITUTION_EMAIL_DOMAINS", "")
    _register(email)
    assert _organization_of(email) is None  # registered before the domain was listed

    monkeypatch.setattr(settings, "INSTITUTION_EMAIL_DOMAINS", "member.example.edu")
    monkeypatch.setattr(server, "_REGISTER_RATE_LIMIT", {})
    _register(email)

    assert _organization_of(email) == org_id


def test_an_admin_created_account_joins_the_admins_organization(
    institution, monkeypatch
) -> None:
    from jose import jwt as jose_jwt

    org_id, emails = institution
    admin = {
        "id": str(uuid.uuid4()),
        "email": "admin@member.example.edu",
        "role": "admin",
        "tenant_id": None,
        "organization_id": org_id,
    }
    monkeypatch.setattr(server, "_authenticate_request", lambda *a, **k: dict(admin))
    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": admin["id"], "exp": now + timedelta(minutes=30), "iat": now},
        settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    client = TestClient(server.app)
    client.cookies.set(server.AUTH_COOKIE_NAME, token)
    email = f"c-{uuid.uuid4().hex[:10]}@anywhere.example.com"
    emails.append(email)

    response = client.post(
        "/api/admin/users",
        json={"email": email, "full_name": "Created By Admin", "password": PASSWORD},
    )

    assert response.status_code == 201, response.text
    assert _organization_of(email) == org_id


# ── Admin page: add or remove a member (PATCH /api/admin/users/{id}) ──


def _admin_client(monkeypatch, admin: dict) -> TestClient:
    from jose import jwt as jose_jwt

    monkeypatch.setattr(server, "_authenticate_request", lambda *a, **k: dict(admin))
    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": admin["id"], "exp": now + timedelta(minutes=30), "iat": now},
        settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    client = TestClient(server.app)
    client.cookies.set(server.AUTH_COOKIE_NAME, token)
    return client


def test_membership_must_be_true_or_false(monkeypatch) -> None:
    """Rejected before any lookup: the string "false" must not count as a value."""
    admin = {
        "id": str(uuid.uuid4()),
        "email": "a@x.edu",
        "role": "admin",
        "tenant_id": None,
    }
    client = _admin_client(monkeypatch, admin)

    response = client.patch(
        f"/api/admin/users/{uuid.uuid4()}", json={"member": "false"}
    )

    assert response.status_code == 400
    assert "member must be true or false" in response.text


def _plain_user(email: str, organization_id=None) -> str:
    with SessionLocal() as db:
        user = User(
            email=email,
            full_name="Plain User",
            password_hash="x",
            role="professor",
            is_active=True,
            organization_id=organization_id,
        )
        db.add(user)
        db.commit()
        return str(user.id)


def test_an_admin_adds_and_removes_a_member(institution, monkeypatch) -> None:
    org_id, emails = institution
    admin = {
        "id": str(uuid.uuid4()),
        "email": "admin@member.example.edu",
        "role": "admin",
        "tenant_id": None,
        "organization_id": org_id,
    }
    client = _admin_client(monkeypatch, admin)
    email = f"n-{uuid.uuid4().hex[:10]}@outside.example.com"
    emails.append(email)
    user_id = _plain_user(email)

    assert (
        client.patch(f"/api/admin/users/{user_id}", json={"member": True}).status_code
        == 200
    )
    assert _organization_of(email) == org_id

    assert (
        client.patch(f"/api/admin/users/{user_id}", json={"member": False}).status_code
        == 200
    )
    assert _organization_of(email) is None


def test_an_admin_cannot_remove_their_own_membership(institution, monkeypatch) -> None:
    org_id, emails = institution
    email = f"self-{uuid.uuid4().hex[:10]}@member.example.edu"
    emails.append(email)
    admin_id = _plain_user(email, organization_id=org_id)
    admin = {
        "id": admin_id,
        "email": email,
        "role": "admin",
        "tenant_id": None,
        "organization_id": org_id,
    }

    response = _admin_client(monkeypatch, admin).patch(
        f"/api/admin/users/{admin_id}", json={"member": False}
    )

    assert response.status_code == 400
    assert _organization_of(email) == org_id


def test_adding_with_no_organization_yet_is_refused(institution, monkeypatch) -> None:
    _, emails = institution
    monkeypatch.setattr(
        server, "_institution_organization_id", lambda db, create=False: None
    )
    admin = {
        "id": str(uuid.uuid4()),
        "email": "a@x.edu",
        "role": "admin",
        "tenant_id": None,
    }
    email = f"none-{uuid.uuid4().hex[:10]}@outside.example.com"
    emails.append(email)
    user_id = _plain_user(email)

    response = _admin_client(monkeypatch, admin).patch(
        f"/api/admin/users/{user_id}", json={"member": True}
    )

    assert response.status_code == 409
    assert _organization_of(email) is None
