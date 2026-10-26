"""Pair review decisions must survive being saved, and set the job status."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from src.backend.api import server
from src.backend.config.settings import settings as app_settings

USER = {"id": str(uuid.uuid4()), "role": "professor", "tenant_id": None}


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "_authenticate_request", lambda *a, **k: dict(USER))
    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": USER["id"], "exp": now + timedelta(minutes=30), "iat": now},
        app_settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    client = TestClient(server.app)
    client.cookies.set(server.AUTH_COOKIE_NAME, token)
    return client


def test_decisions_persist_and_drive_the_job_status(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(server, "_jobs", {})
    job_id = str(uuid.uuid4())
    server._jobs[job_id] = {
        "id": job_id,
        "status": "completed",
        "threshold": 0.5,
        "owner_user_id": USER["id"],
        "results": [
            {"file_a": "a.py", "file_b": "b.py", "score": 0.9},
            {"file_a": "a.py", "file_b": "c.py", "score": 0.8},
        ],
    }
    server._persist_job(job_id)
    client = _client(monkeypatch)

    for key, status in (("a.py::b.py", "confirmed"), ("a.py::c.py", "dismissed")):
        response = client.patch(
            f"/api/job/{job_id}/review",
            json={"pair_reviews": {key: {"status": status}}},
        )
        assert response.status_code == 200, response.text

    job = server._get_job(job_id)
    statuses = {r["file_b"]: r.get("review_status") for r in job["results"]}
    assert statuses == {"b.py": "confirmed", "c.py": "dismissed"}
    # The dismissal came last, but a confirmed pair keeps the job confirmed.
    assert job["review_status"] == "confirmed"
    on_disk = json.loads(server._job_metadata_path(job_id).read_text())
    assert {r["file_b"]: r.get("review_status") for r in on_disk["results"]} == statuses
