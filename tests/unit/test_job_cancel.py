"""Unit tests for job cancellation and the queue overview (real DB rows)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from src.backend.api import server
from src.backend.config.database import SessionLocal
from src.backend.models.database import Job, Tenant, User


def _cookie_jar() -> dict[str, str]:
    """Return a valid session cookie accepted by the auth middleware."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    from src.backend.api.server import AUTH_COOKIE_NAME
    from src.backend.config.settings import settings as app_settings

    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": "admin-1", "exp": now + timedelta(minutes=30), "iat": now},
        app_settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    return {AUTH_COOKIE_NAME: token}


def _fake_admin(*args, **kwargs):
    return {"id": "admin-1", "role": "admin"}


def _fake_professor(*args, **kwargs):
    return {"id": "prof-1", "role": "professor"}


def _make_tenant(db, tag: str):
    """Create a tenant + admin user with collision-proof identifiers."""
    tenant = Tenant(
        name=f"Cancel Workspace {tag}",
        api_key_hash=f"test-hash-{uuid.uuid4().hex}",
    )
    db.add(tenant)
    db.flush()
    db.add(
        User(
            tenant_id=tenant.id,
            email=f"cancel-{tag}-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Cancel Admin",
            password_hash="already-hashed",
            role="admin",
            is_active=True,
        )
    )
    db.commit()
    return tenant


def _make_job(db, tenant_id, status: str, tag: str) -> str:
    """Create a job row and return its id."""
    job_id = f"cancel-{tag}-{uuid.uuid4().hex[:8]}"
    db.add(Job(id=job_id, tenant_id=tenant_id, name=f"Cancel job {tag}", status=status))
    db.commit()
    return job_id


class TestCancelJobEndpoint:
    """POST /api/jobs/{id}/cancel behavior."""

    def test_cancel_queued_job(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a queued job flips to cancelled in the DB."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        with SessionLocal() as db:
            tenant = _make_tenant(db, "queued")
            job_id = _make_job(db, tenant.id, "queued", "q1")
        client = TestClient(server.app)
        response = client.post(f"/api/jobs/{job_id}/cancel", cookies=_cookie_jar())
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "cancelled"
        with SessionLocal() as db:
            row = db.query(Job).filter(Job.id == job_id).first()
            assert row is not None and row.status == "cancelled"

    def test_cancel_unknown_job_is_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an unknown id returns 404, not 500."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        client = TestClient(server.app)
        response = client.post("/api/jobs/does-not-exist/cancel", cookies=_cookie_jar())
        assert response.status_code == 404

    def test_cancel_completed_job_conflicts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that terminal jobs cannot be cancelled."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        with SessionLocal() as db:
            tenant = _make_tenant(db, "done")
            job_id = _make_job(db, tenant.id, "completed", "c1")
        client = TestClient(server.app)
        response = client.post(f"/api/jobs/{job_id}/cancel", cookies=_cookie_jar())
        assert response.status_code == 409

    def test_cancel_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot cancel jobs."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.post("/api/jobs/anything/cancel", cookies=_cookie_jar())
        assert response.status_code == 403


class TestJobQueueEndpoint:
    """GET /api/jobs/queue behavior."""

    def test_queue_overview_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the overview carries counts, workers and active jobs."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        with SessionLocal() as db:
            tenant = _make_tenant(db, "queue")
            mine = {
                _make_job(db, tenant.id, "queued", "qq"),
                _make_job(db, tenant.id, "processing", "qp"),
            }
        client = TestClient(server.app)
        response = client.get("/api/jobs/queue", cookies=_cookie_jar())
        assert response.status_code == 200, response.text
        body = response.json()
        assert "db_counts" in body and "workers" in body
        assert "celery_error" in body and "active_jobs" in body
        assert "checked_at" in body
        assert body["db_counts"].get("queued", 0) >= 1
        returned_ids = {job["id"] for job in body["active_jobs"]}
        assert mine <= returned_ids

    def test_queue_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot view the queue."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.get("/api/jobs/queue", cookies=_cookie_jar())
        assert response.status_code == 403


class TestCooperativeCancel:
    """Flag checks and stage-guard behavior."""

    def test_job_cancelled_flag(self) -> None:
        """Test that the flag follows the DB row and tolerates ghosts."""
        with SessionLocal() as db:
            tenant = _make_tenant(db, "flag")
            cancelled_id = _make_job(db, tenant.id, "cancelled", "f1")
            queued_id = _make_job(db, tenant.id, "queued", "f2")
        assert server._job_cancelled(cancelled_id) is True
        assert server._job_cancelled(queued_id) is False
        assert server._job_cancelled("ghost-job-id") is False

    def test_stage_change_raises_when_cancelled(self) -> None:
        """Test that a stage transition aborts a cancelled job."""
        with SessionLocal() as db:
            tenant = _make_tenant(db, "stage")
            job_id = _make_job(db, tenant.id, "queued", "s1")
            # Simulate the admin kill landing in the DB first.
            row = db.query(Job).filter(Job.id == job_id).first()
            assert row is not None
            row.status = "cancelled"
            db.commit()
        server._jobs[job_id] = {"id": job_id, "progress": {"stage": "queued"}}
        try:
            with pytest.raises(server._JobCancelled):
                server._set_job_progress(job_id, "reading_submissions")
            # Same-stage ticks never consult the flag.
            server._set_job_progress(job_id, "queued")
        finally:
            server._jobs.pop(job_id, None)

    def test_stage_change_proceeds_when_live(self) -> None:
        """Test that uncancelled jobs pass the guard untouched."""
        with SessionLocal() as db:
            tenant = _make_tenant(db, "live")
            job_id = _make_job(db, tenant.id, "queued", "s2")
        server._jobs[job_id] = {"id": job_id, "progress": {"stage": "queued"}}
        try:
            server._set_job_progress(job_id, "reading_submissions")
            assert server._jobs[job_id]["progress"]["stage"] == "reading_submissions"
        finally:
            server._jobs.pop(job_id, None)

    def test_background_wrapper_keeps_cancelled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a cancelled pipeline never becomes failed."""
        job_id = "cancel-bg-test"

        async def boom(*args, **kwargs):
            raise server._JobCancelled(job_id)

        monkeypatch.setattr(server, "_run_analysis", boom)
        server._jobs[job_id] = {"id": job_id, "status": "cancelled"}
        try:
            server._run_analysis_background(job_id, ".")
            assert server._jobs[job_id]["status"] == "cancelled"
        finally:
            server._jobs.pop(job_id, None)


class TestCancelAllJobsEndpoint:
    """POST /api/jobs/cancel-all behavior."""

    def test_cancels_active_leaves_terminal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that active jobs cancel while terminal rows are untouched."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        with SessionLocal() as db:
            tenant = _make_tenant(db, "bulk")
            mine_active = {
                _make_job(db, tenant.id, "queued", "bq"),
                _make_job(db, tenant.id, "processing", "bp"),
            }
            mine_done = _make_job(db, tenant.id, "completed", "bd")
            mine_failed = _make_job(db, tenant.id, "failed", "bf")
        client = TestClient(server.app)
        response = client.post("/api/jobs/cancel-all", cookies=_cookie_jar())
        assert response.status_code == 200, response.text
        body = response.json()
        assert mine_active <= set(body["cancelled"])
        with SessionLocal() as db:
            statuses = {
                row.id: row.status
                for row in db.query(Job)
                .filter(Job.id.in_(list(mine_active) + [mine_done, mine_failed]))
                .all()
            }
        assert all(statuses[job_id] == "cancelled" for job_id in mine_active)
        assert statuses[mine_done] == "completed"
        assert statuses[mine_failed] == "failed"

    def test_cancel_all_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot bulk-cancel jobs."""
        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.post("/api/jobs/cancel-all", cookies=_cookie_jar())
        assert response.status_code == 403
