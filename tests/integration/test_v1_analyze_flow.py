"""
Integration tests for the public REST API analyze flow (POST /api/v1/analyze).

Verifies that the endpoint:
- authenticates via API key,
- validates the request,
- materializes submissions to the job's submissions directory with safe,
  pipeline-readable names,
- queues the shared background pipeline (`_run_analysis_background`),
- exposes job status via GET /api/v1/jobs/{id}.

The heavy analysis pipeline itself is stubbed; a full pipeline run is covered
by the upload flow and manual smoke tests.

Run with: pytest tests/integration/test_v1_analyze_flow.py
"""

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _db_available() -> bool:
    """Check whether the configured database is reachable."""
    try:
        from src.backend.config.database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception:
        return False


@pytest.fixture(scope="module")
def client():
    """Test client bound to the real API app."""
    from src.backend.api import server

    with TestClient(server.app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def require_db():
    """Skip module tests if the database is unavailable."""
    if not _db_available():
        pytest.skip("Database is not reachable — skipping database-dependent tests")


def _create_tenant(name: str) -> str:
    """Create a throwaway tenant row and return its UUID."""
    from src.backend.config.database import SessionLocal
    from src.backend.infrastructure.db import TenantService

    with SessionLocal() as db:
        tenant = TenantService.create_tenant(
            db=db, name=name, api_key_hash=f"test-{uuid.uuid4().hex}"
        )
        return str(tenant.id)


def _delete_tenant(tenant_id: str) -> None:
    """Remove a throwaway tenant row (best effort)."""
    try:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Tenant

        with SessionLocal() as db:
            db.query(Tenant).filter(Tenant.id == tenant_id).delete()
            db.commit()
    except Exception:
        pass


@pytest.fixture(scope="module")
def tenant_id():
    """A dedicated tenant for this test module (created once, deleted after)."""
    tid = _create_tenant("v1-analyze-flow-tests")
    yield tid
    _delete_tenant(tid)


@pytest.fixture()
def api_key(tenant_id):
    """Register a short-lived API key for the test tenant."""
    from src.backend.api.middleware.auth import api_key_manager

    key = api_key_manager.create_key(
        name="v1-analyze-flow-test",
        tenant_id=tenant_id,
        rate_limit=1000,
        rate_window=60,
    )
    yield key
    api_key_manager.revoke_key(key)


@pytest.fixture()
def stub_pipeline(monkeypatch):
    """Replace the heavy background pipeline with an argument-capturing stub.

    The analyze endpoint imports `_run_analysis_background` lazily from the
    server module on every request, so patching the module attribute is
    picked up per-request.
    """
    from src.backend.api import server

    captured: dict = {}

    def _stub(job_id, job_dir, *args, **kwargs):
        captured["job_id"] = job_id
        captured["job_dir"] = Path(job_dir)

    monkeypatch.setattr(server, "_run_analysis_background", _stub)
    return captured


def _cleanup_job(job_id: str, job_dir: Path | None) -> None:
    """Remove DB rows and on-disk artifacts created by a test job."""
    try:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Job, SimilarityResult, Submission

        with SessionLocal() as db:
            db.query(SimilarityResult).filter(
                SimilarityResult.job_id == job_id
            ).delete()
            db.query(Submission).filter(Submission.job_id == job_id).delete()
            db.query(Job).filter(Job.id == job_id).delete()
            db.commit()
    except Exception:
        pass
    if job_dir is not None:
        # reports/<job_id>/ is the job's root (submissions live under it).
        shutil.rmtree(job_dir.parent, ignore_errors=True)


def _analyze_payload() -> dict:
    """Build a valid analyze request with edge-case submission names."""
    return {
        "name": "v1 analyze flow test",
        "submissions": [
            {"name": "student1_solution.py", "content": "def f():\n    return 1\n"},
            {"name": "student2_solution.py", "content": "def g():\n    return 2\n"},
            # No extension: must be coerced to a pipeline-readable `.py` file.
            {"name": "student3", "content": "def h():\n    return 3\n"},
            # Path traversal attempt: must be contained in the job directory.
            {"name": "../evil.py", "content": "def e():\n    return 4\n"},
        ],
        "threshold": 0.5,
    }


class TestV1AnalyzeFlow:
    """End-to-end wiring tests for the public REST analyze API."""

    def test_analyze_requires_api_key(self, client, require_db):
        """Requests without an API key are rejected with 401."""
        response = client.post("/api/v1/analyze", json=_analyze_payload())
        assert response.status_code == 401

    def test_analyze_rejects_single_submission(self, client, require_db, api_key):
        """Fewer than two submissions is a 400 validation error."""
        response = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": api_key},
            json={
                "name": "too few",
                "submissions": [{"name": "a.py", "content": "x = 1"}],
            },
        )
        assert response.status_code == 400

    def test_analyze_creates_job_and_materializes_submissions(
        self, client, require_db, api_key, stub_pipeline
    ):
        """A valid request creates a job, writes safe submission files, and
        queues the shared background pipeline."""
        response = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": api_key},
            json=_analyze_payload(),
        )
        assert response.status_code == 201, response.text
        data = response.json()

        assert data["status"] == "queued"
        assert data["submission_count"] == 4
        assert data["status_url"].endswith(f"/api/v1/jobs/{data['job_id']}")
        assert "estimated_completion" in data

        # The background pipeline was queued with the created job id.
        assert stub_pipeline.get("job_id") == data["job_id"]

        # Submissions were materialized with safe, pipeline-readable names.
        job_dir = stub_pipeline.get("job_dir")
        assert job_dir is not None and job_dir.is_dir()
        on_disk = sorted(p.name for p in job_dir.iterdir())
        assert on_disk == [
            "evil.py",  # traversal contained inside the job dir
            "student1_solution.py",
            "student2_solution.py",
            "student3.py",  # extension coerced
        ]

        # The DB job row exists with a queued status.
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Job

        with SessionLocal() as db:
            job = db.query(Job).filter(Job.id == data["job_id"]).first()
        assert job is not None
        assert job.status == "queued"

        _cleanup_job(data["job_id"], job_dir)

    def test_job_status_endpoint_after_completion(
        self, client, require_db, api_key, stub_pipeline
    ):
        """GET /api/v1/jobs/{id} reports completion once the pipeline marks
        the job completed in the database."""
        response = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": api_key},
            json=_analyze_payload(),
        )
        assert response.status_code == 201, response.text
        data = response.json()
        job_id = data["job_id"]
        job_dir = stub_pipeline.get("job_dir")

        # Simulate the pipeline's completion persistence
        # (`_update_job_status_in_db(job_id, "completed")`).
        from datetime import datetime

        from src.backend.config.database import SessionLocal
        from src.backend.models.database import Job

        with SessionLocal() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            job.status = "completed"
            job.completed_at = datetime.now()
            db.commit()

        status_response = client.get(data["status_url"], headers={"X-API-Key": api_key})
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["job_id"] == job_id
        assert status_data["status"] == "completed"
        assert isinstance(status_data["results"], list)

        _cleanup_job(job_id, job_dir)

    def test_job_status_isolated_per_tenant(
        self, client, require_db, api_key, stub_pipeline
    ):
        """A different tenant's API key cannot read this tenant's job."""
        from src.backend.api.middleware.auth import api_key_manager

        response = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": api_key},
            json=_analyze_payload(),
        )
        assert response.status_code == 201, response.text
        data = response.json()
        job_id = data["job_id"]
        job_dir = stub_pipeline.get("job_dir")

        other_tenant_id = _create_tenant("v1-analyze-other-tenant")
        other_key = api_key_manager.create_key(
            name="other-tenant", tenant_id=other_tenant_id
        )
        try:
            foreign = client.get(data["status_url"], headers={"X-API-Key": other_key})
            assert foreign.status_code == 404
        finally:
            api_key_manager.revoke_key(other_key)
            _delete_tenant(other_tenant_id)
            _cleanup_job(job_id, job_dir)
