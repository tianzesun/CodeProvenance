"""An upload may only be filed under an assignment the uploader can read."""

import pytest
from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.application.services import academic_access

FILES = [
    ("files", ("a.py", "print('a')\n", "text/x-python")),
    ("files", ("b.py", "print('b')\n", "text/x-python")),
]


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    captured: dict = {}
    monkeypatch.setattr(server, "dispatch_analysis", lambda **kw: captured.update(kw))
    monkeypatch.setattr(server, "_jobs", dict(server._jobs))
    monkeypatch.setattr(server, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(
        academic_access, "course_id_for_assignment", lambda db, aid: "course-1"
    )
    test_client = TestClient(server.app)
    assert test_client.post("/api/auth/guest").status_code == 200
    test_client.captured = captured
    return test_client


@pytest.mark.parametrize("path", ["/api/upload", "/api/upload-zip"])
def test_unreadable_assignment_is_rejected(client, monkeypatch, path) -> None:
    monkeypatch.setattr(academic_access, "can_read_course", lambda db, u, c: False)
    files = (
        FILES
        if path == "/api/upload"
        else [("file", ("sub.zip", b"PK\x05\x06" + b"\0" * 18, "application/zip"))]
    )

    response = client.post(path, files=files, data={"assignment_id": "other-tenant"})

    assert response.status_code == 403
    assert client.captured == {}


def test_readable_assignment_is_accepted(client, monkeypatch) -> None:
    monkeypatch.setattr(academic_access, "can_read_course", lambda db, u, c: True)

    response = client.post("/api/upload", files=FILES, data={"assignment_id": "mine"})

    assert response.status_code == 200, response.text
    assert client.captured["assignment_id"] == "mine"


def test_unknown_assignment_is_rejected(client, monkeypatch) -> None:
    monkeypatch.setattr(
        academic_access, "course_id_for_assignment", lambda db, aid: None
    )

    response = client.post("/api/upload", files=FILES, data={"assignment_id": "gone"})

    assert response.status_code == 403
