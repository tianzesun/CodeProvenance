"""The upload page and jobs must say when engine weights are not used."""

from fastapi.testclient import TestClient

from src.backend.api import server


def test_status_lists_the_learned_model_signals() -> None:
    server._learned_scoring_status.cache_clear()
    status = server._learned_scoring_status()

    # The shipped artifact is present in the repository.
    assert status["active"] is True
    assert "Winnowing" in status["signals"]
    assert "Logic flow" in status["signals"]


def test_upload_settings_expose_the_learned_scoring_status() -> None:
    client = TestClient(server.app)
    assert client.post("/api/auth/guest").status_code == 200

    body = client.get("/api/upload-settings").json()

    assert body["learned_scoring"] == server._learned_scoring_status()
