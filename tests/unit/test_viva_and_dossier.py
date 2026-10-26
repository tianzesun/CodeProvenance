"""Viva outcome validation and a dossier that reflects the latest outcomes."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from src.backend.api import server
from src.backend.config.settings import settings as app_settings
from src.backend.evaluation import evidence_dossier
from src.backend.infrastructure.reporting import dossier_pdf_exporter

USER = {"id": str(uuid.uuid4()), "role": "professor", "tenant_id": None}


@pytest.fixture
def job_id(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(server, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(server, "_jobs", {})
    job_id = str(uuid.uuid4())
    server._jobs[job_id] = {
        "id": job_id,
        "status": "completed",
        "owner_user_id": USER["id"],
        "results": [{"file_a": "alice.py", "file_b": "bob.py", "score": 0.9}],
    }
    return job_id


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "_authenticate_request", lambda *a, **k: dict(USER))
    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": USER["id"], "exp": now + timedelta(minutes=30), "iat": now},
        app_settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    test_client = TestClient(server.app)
    test_client.cookies.set(server.AUTH_COOKIE_NAME, token)
    return test_client


@pytest.mark.parametrize(
    "body",
    [
        {"submission_name": "mallory.py", "outcome": "inconclusive"},  # not in job
        {"submission_name": "alice.py" * 100, "outcome": "inconclusive"},
        {
            "submission_name": "alice.py",
            "outcome": "inconclusive",
            "conducted_at": "2026-10-25T10:00:00",  # no timezone
        },
    ],
)
def test_invalid_viva_input_is_a_400(client, job_id, body) -> None:
    assert client.put(f"/api/job/{job_id}/viva", json=body).status_code == 400


def test_malformed_viva_json_is_a_400(client, job_id) -> None:
    response = client.put(
        f"/api/job/{job_id}/viva",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_dossier_pdf_is_rebuilt_not_served_from_cache(
    client, job_id, monkeypatch, tmp_path
) -> None:
    stale = tmp_path / "stale.pdf"
    stale.write_bytes(b"%PDF-stale")
    monkeypatch.setattr(server, "_resolve_cached_report", lambda *a: stale)
    monkeypatch.setattr(server, "_load_viva_outcomes", lambda job: {})
    monkeypatch.setattr(
        evidence_dossier.EvidenceDossierService, "build", lambda self, job, **kw: {}
    )
    monkeypatch.setattr(
        dossier_pdf_exporter.DossierPdfExporter,
        "export_pdf",
        lambda self, dossier: b"%PDF-fresh",
    )

    response = client.get(f"/dossier/{job_id}/download-pdf")

    assert response.status_code == 200
    assert response.content == b"%PDF-fresh"
