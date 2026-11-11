"""The upload page and jobs must say when engine weights are not used."""

from fastapi.testclient import TestClient

from src.backend.api import server


def test_status_lists_the_learned_model_signals() -> None:
    server._learned_scoring_status.cache_clear()
    status = server._learned_scoring_status()

    # The shipped artifact is present in the repository.
    assert status["active"] is True
    assert "Chunk hash match" in status["signals"]
    assert "Logic flow" in status["signals"]


def test_status_reports_what_the_model_weighs_strongest_first() -> None:
    server._learned_scoring_status.cache_clear()
    influence = server._learned_scoring_status()["influence"]

    weights = [item["weight"] for item in influence]
    assert weights == sorted(weights, reverse=True)
    from src.backend.engines.scoring.learned_fusion import LearnedFusionScorer

    assert {item["key"] for item in influence} == set(
        LearnedFusionScorer().feature_names
    )
    # The shipped model leans on copied passages, not on semantic similarity.
    assert influence[0]["key"] == "winnowing"
    by_key = {item["key"]: item["weight"] for item in influence}
    assert abs(by_key["embedding"]) < 0.5


def test_no_model_means_no_influence(monkeypatch) -> None:
    from src.backend.engines.scoring import learned_fusion

    monkeypatch.setattr(learned_fusion.LearnedFusionScorer, "available", False)
    server._learned_scoring_status.cache_clear()
    try:
        assert server._learned_scoring_status() == {
            "active": False,
            "signals": [],
            "influence": [],
        }
    finally:
        server._learned_scoring_status.cache_clear()


def test_upload_settings_expose_the_learned_scoring_status() -> None:
    client = TestClient(server.app)
    assert client.post("/api/auth/guest").status_code == 200

    body = client.get("/api/upload-settings").json()

    assert body["learned_scoring"] == server._learned_scoring_status()
