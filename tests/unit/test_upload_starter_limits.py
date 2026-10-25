"""Starter files get the same per-file limits as submissions."""

import pytest
from fastapi.testclient import TestClient

from src.backend.api import server

SUBMISSIONS = [
    ("files", ("a.py", "print('a')\n", "text/x-python")),
    ("files", ("b.py", "print('b')\n", "text/x-python")),
]


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    captured: dict = {}
    monkeypatch.setattr(server, "dispatch_analysis", lambda **kw: captured.update(kw))
    monkeypatch.setattr(server, "_jobs", dict(server._jobs))
    monkeypatch.setattr(server, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(server.settings, "MAX_FILE_SIZE_MB", 1)
    test_client = TestClient(server.app)
    assert test_client.post("/api/auth/guest").status_code == 200
    test_client.captured = captured
    return test_client


def test_oversized_starter_file_is_rejected(client: TestClient, tmp_path) -> None:
    big = "x = 1\n" * 200_000  # ~1.2 MB, over the patched 1 MB limit
    response = client.post(
        "/api/upload",
        files=[*SUBMISSIONS, ("starter_files", ("starter.py", big, "text/x-python"))],
    )

    assert response.status_code == 400
    assert "Starter code" in response.json()["error"]
    assert client.captured == {}
    assert not any((tmp_path / "uploads").iterdir())


def test_starter_within_limits_is_passed_to_the_analysis(client: TestClient) -> None:
    response = client.post(
        "/api/upload",
        files=[
            *SUBMISSIONS,
            (
                "starter_files",
                ("starter.py", "def main():\n    pass\n", "text/x-python"),
            ),
        ],
    )

    assert response.status_code == 200, response.text
    assert client.captured["starter_sources"] == ["def main():\n    pass\n"]
