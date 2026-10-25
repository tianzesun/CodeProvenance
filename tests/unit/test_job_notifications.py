"""Finish notifications: signed webhook and owner email, without student details."""

import json

import pytest

from src.backend.application.services import job_notifications
from src.backend.config.settings import settings, workspace_overrides

JOB = {
    "id": "job-1",
    "status": "completed",
    "course_name": "CSC108",
    "assignment_name": "A1",
    "file_count": 3,
    "owner_user_id": "u-1",
    "summary": {"total_pairs": 3, "suspicious_pairs": 1},
    "results": [{"file_a": "alice.py", "file_b": "bob.py", "score": 0.9}],
    "submissions": {"alice.py": "print(1)", "bob.py": "print(1)"},
}


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def posted(monkeypatch):
    captured: list = []

    def fake_urlopen(request, timeout=None):
        captured.append(request)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        job_notifications, "_resolves_to_public_hosts", lambda url: True
    )
    return captured


def test_the_payload_has_counts_and_a_link_but_no_student_details() -> None:
    payload = job_notifications.build_payload(JOB, "https://desk.example.edu/")

    assert payload["event"] == "analysis.completed"
    assert payload["pairs_flagged"] == 1
    assert payload["submissions"] == 3
    assert payload["results_url"] == "https://desk.example.edu/results/job-1"
    text = json.dumps(payload)
    assert "alice" not in text and "print(1)" not in text


def test_the_workspace_webhook_gets_a_signed_post(posted, monkeypatch) -> None:
    monkeypatch.setenv("WEBHOOK_SECRET_KEY", "shh")

    with workspace_overrides({"WEBHOOK_URL": "https://hooks.example.com/a"}):
        sent = job_notifications.notify_job_finished(dict(JOB), email_owner=False)

    assert sent == {"webhook": True, "email": False}
    request = posted[0]
    assert request.full_url == "https://hooks.example.com/a"
    headers = {k.lower(): v for k, v in request.header_items()}
    assert headers["x-integritydesk-signature"] == job_notifications.sign(
        request.data, headers["x-integritydesk-timestamp"], "shh"
    )


def test_no_webhook_url_means_no_post(posted, override_setting) -> None:
    override_setting("WEBHOOK_URL", "")

    sent = job_notifications.notify_job_finished(dict(JOB), email_owner=False)

    assert sent["webhook"] is False
    assert posted == []


@pytest.mark.parametrize(
    "url", ["http://hooks.example.com/a", "https://localhost/a", "https://10.0.0.5/a"]
)
def test_private_or_plain_http_urls_are_never_called(posted, url) -> None:
    assert job_notifications.post_webhook(url, {"event": "x"}) is False
    assert posted == []


def test_a_host_resolving_to_a_private_address_is_not_called(monkeypatch) -> None:
    called = []
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: called.append(a))
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("10.1.2.3", 0))],
    )

    assert job_notifications.post_webhook("https://hooks.example.com/a", {}) is False
    assert called == []


def test_guest_and_unfinished_jobs_send_nothing(posted) -> None:
    with workspace_overrides({"WEBHOOK_URL": "https://hooks.example.com/a"}):
        job_notifications.notify_job_finished(dict(JOB, guest=True), email_owner=True)
        job_notifications.notify_job_finished(
            dict(JOB, status="processing"), email_owner=True
        )

    assert posted == []


def test_the_owner_is_emailed_when_the_workspace_asks(monkeypatch) -> None:
    from src.backend.infrastructure.email_service import EmailService

    sent_to = []

    async def fake_send(to, **kwargs):
        sent_to.append((to, kwargs))
        return True

    monkeypatch.setattr(
        job_notifications, "_owner_email", lambda job: "prof@example.edu"
    )
    monkeypatch.setattr(EmailService, "send_analysis_finished_email", fake_send)

    with workspace_overrides({"WEBHOOK_URL": ""}):
        quiet = job_notifications.notify_job_finished(dict(JOB), email_owner=False)
        told = job_notifications.notify_job_finished(dict(JOB), email_owner=True)

    assert quiet["email"] is False and told["email"] is True
    to, kwargs = sent_to[0]
    assert to == "prof@example.edu"
    assert kwargs["title"] == "CSC108 · A1"
    assert kwargs["flagged_pairs"] == 1


def test_the_finished_email_escapes_names() -> None:
    import asyncio

    from src.backend.infrastructure import email_service

    captured = {}

    async def fake_deliver(to, subject, html_body, text_body):
        captured["html"] = html_body
        return True

    original = email_service.EmailService._deliver
    email_service.EmailService._deliver = staticmethod(fake_deliver)
    try:
        asyncio.run(
            email_service.EmailService.send_analysis_finished_email(
                "p@example.edu",
                title="<script>x</script>",
                succeeded=True,
                submissions=2,
                flagged_pairs=0,
                results_url="https://desk.example.edu/results/1",
            )
        )
    finally:
        email_service.EmailService._deliver = original

    assert "<script>" not in captured["html"]


def test_the_email_password_is_sent_unmasked(override_setting) -> None:
    from pydantic import SecretStr

    from src.backend.infrastructure.email_service import EmailService

    override_setting("EMAIL_PASSWORD", SecretStr("real-password"))

    assert EmailService._get_smtp_config()["password"] == "real-password"


def test_settings_reject_a_webhook_that_is_not_public_https() -> None:
    from src.backend.api import server

    with pytest.raises(ValueError):
        server.SETTINGS_VALIDATORS["webhook_url"]("http://hooks.example.com")
    with pytest.raises(ValueError):
        server.SETTINGS_VALIDATORS["webhook_url"]("https://127.0.0.1/x")
    assert settings is not None


def _admin_client(monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone

    from fastapi.testclient import TestClient
    from jose import jwt as jose_jwt

    from src.backend.api import server

    admin = {"id": str(uuid.uuid4()), "role": "admin", "tenant_id": None}
    monkeypatch.setattr(server, "_authenticate_request", lambda *a, **k: dict(admin))
    monkeypatch.setattr(server, "_require_current_user", lambda *a, **k: dict(admin))
    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": admin["id"], "exp": now + timedelta(minutes=30), "iat": now},
        settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    client = TestClient(server.app)
    client.cookies.set(server.AUTH_COOKIE_NAME, token)
    return client


def test_the_test_button_posts_to_the_saved_webhook(monkeypatch, override_setting):
    sent = []
    monkeypatch.setattr(
        job_notifications, "post_webhook", lambda url, payload: sent.append(url) or True
    )
    override_setting("WEBHOOK_URL", "https://hooks.example.com/t")

    response = _admin_client(monkeypatch).post("/api/settings/webhook/test", json={})

    assert response.json()["ok"] is True
    assert sent == ["https://hooks.example.com/t"]


def test_the_test_button_needs_a_saved_url(monkeypatch, override_setting):
    override_setting("WEBHOOK_URL", "")

    response = _admin_client(monkeypatch).post("/api/settings/webhook/test", json={})

    assert response.json()["ok"] is False
