"""Unit tests for the stuck-queue watchdog (no real webhooks sent)."""

import uuid
from datetime import datetime, timedelta

import pytest

from src.backend.config.database import SessionLocal
from src.backend.config.settings import settings as app_settings
from src.backend.models.database import Job, Tenant, User
from src.backend.workers import queue_watchdog as watchdog


@pytest.fixture(autouse=True)
def _quiet_worker_probe(monkeypatch):
    """Keep tests hermetic: no real broker contact, instant answers."""
    from src.backend.integrations import system_status

    async def fake_check_celery():
        return {"status": "up", "label": "Celery workers", "detail": ""}

    monkeypatch.setattr(system_status, "check_celery", fake_check_celery)
    watchdog.reset_alert_state()
    yield
    watchdog.reset_alert_state()


def _delete_watchdog_rows() -> None:
    """Remove watchdog-tagged rows so tests never see each other's jobs."""
    from src.backend.models.database import Tenant, User

    with SessionLocal() as db:
        db.query(Job).filter(Job.id.like("watchdog-%")).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.email.like("watchdog-%@%")).delete(
            synchronize_session=False
        )
        db.query(Tenant).filter(Tenant.name.like("Watchdog Workspace %")).delete(
            synchronize_session=False
        )
        db.commit()


@pytest.fixture(autouse=True)
def _isolated_watchdog_rows():
    """Each test starts with no watchdog rows from earlier tests."""
    _delete_watchdog_rows()
    yield
    _delete_watchdog_rows()


def _make_tenant(db, tag: str):
    """Create a tenant + admin user with collision-proof identifiers."""
    tenant = Tenant(
        name=f"Watchdog Workspace {tag}",
        api_key_hash=f"test-hash-{uuid.uuid4().hex}",
    )
    db.add(tenant)
    db.flush()
    db.add(
        User(
            tenant_id=tenant.id,
            email=f"watchdog-{tag}-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Watchdog Admin",
            password_hash="already-hashed",
            role="admin",
            is_active=True,
        )
    )
    db.commit()
    return tenant


def _make_job(db, tenant_id, status: str, tag: str, age: timedelta | None = None):
    """Create a job row, optionally backdated, and return its id."""
    from datetime import timezone

    job_id = f"watchdog-{tag}-{uuid.uuid4().hex[:8]}"
    row = Job(id=job_id, tenant_id=tenant_id, name=f"Watchdog job {tag}", status=status)
    if age is not None:
        # Timezone-aware: naive datetimes are interpreted as UTC by Postgres,
        # silently shifting local wall-clock times by the UTC offset.
        row.created_at = datetime.now(timezone.utc) - age
    db.add(row)
    db.commit()
    return job_id


class FakeResponse:
    """Minimal urlopen context manager returning a fixed status."""

    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestStuckScan:
    """Age/threshold detection against real DB rows."""

    def test_old_queued_job_is_stuck(self) -> None:
        """Test that a long-queued job is reported with its age."""
        with SessionLocal() as db:
            tenant = _make_tenant(db, "oldq")
            job_id = _make_job(db, tenant.id, "queued", "oq", timedelta(hours=2))
            fresh_id = _make_job(db, tenant.id, "queued", "fq")
        stuck = watchdog._stuck_jobs()
        ids = {job["id"] for job in stuck}
        assert job_id in ids
        assert fresh_id not in ids
        assert next(j for j in stuck if j["id"] == job_id)["age_seconds"] > 3600

    def test_processing_gets_a_longer_threshold(self) -> None:
        """Test that running jobs tolerate longer runtimes than queued ones."""
        with SessionLocal() as db:
            tenant = _make_tenant(db, "proc")
            old_running = _make_job(
                db, tenant.id, "processing", "op", timedelta(hours=3)
            )
            young_running = _make_job(
                db, tenant.id, "processing", "yp", timedelta(minutes=45)
            )
        ids = {job["id"] for job in watchdog._stuck_jobs()}
        assert old_running in ids
        assert young_running not in ids

    def test_scan_never_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a database outage yields [], not an exception."""
        from src.backend.config import database as database_module

        def boom(*args, **kwargs):
            raise RuntimeError("db gone")

        monkeypatch.setattr(database_module, "SessionLocal", boom)
        assert watchdog._stuck_jobs() == []


class TestAlertDelivery:
    """Alert-once semantics with a captured (fake) webhook receiver."""

    def _capture_post(self, monkeypatch, status: int = 200):
        """Capture POST payloads instead of sending them."""
        captured: list = []

        def fake_urlopen(request, timeout=None):
            captured.append(
                {"url": request.full_url, "body": request.data.decode("utf-8")}
            )
            return FakeResponse(status)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        return captured

    def test_alerts_once_then_recovers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test alert-once, forget-on-recovery, and re-alert on relapse."""
        monkeypatch.setattr(
            app_settings, "WEBHOOK_URL", "https://hooks.example.com/stuck"
        )
        posted = self._capture_post(monkeypatch)
        with SessionLocal() as db:
            tenant = _make_tenant(db, "relapse")
            job_id = _make_job(db, tenant.id, "queued", "r1", timedelta(hours=2))

        first = watchdog.check_and_alert()
        assert first["alerted"] == [job_id]
        assert len(posted) == 1

        second = watchdog.check_and_alert()
        assert second["alerted"] == []
        assert len(posted) == 1

        with SessionLocal() as db:
            row = db.query(Job).filter(Job.id == job_id).first()
            assert row is not None
            row.status = "completed"
            db.commit()
        assert watchdog.check_and_alert()["alerted"] == []

        with SessionLocal() as db:
            row = db.query(Job).filter(Job.id == job_id).first()
            assert row is not None
            row.status = "queued"
            db.commit()
        assert watchdog.check_and_alert()["alerted"] == [job_id]
        assert len(posted) == 2

    def test_no_url_means_no_post(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a missing webhook URL only logs, never sends."""
        monkeypatch.setattr(app_settings, "WEBHOOK_URL", "")
        posted = self._capture_post(monkeypatch)
        with SessionLocal() as db:
            tenant = _make_tenant(db, "nourl")
            job_id = _make_job(db, tenant.id, "queued", "nu", timedelta(hours=2))
        summary = watchdog.check_and_alert()
        assert any(job["id"] == job_id for job in summary["stuck"])
        assert summary["alerted"] == []
        assert posted == []

    def test_rejected_receiver_retries_next_round(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a failed POST does not consume the alert."""
        monkeypatch.setattr(
            app_settings, "WEBHOOK_URL", "https://hooks.example.com/stuck"
        )
        posted = self._capture_post(monkeypatch, status=500)
        with SessionLocal() as db:
            tenant = _make_tenant(db, "retry")
            job_id = _make_job(db, tenant.id, "queued", "rt", timedelta(hours=2))
        assert watchdog.check_and_alert()["alerted"] == []
        assert len(posted) == 1
        assert watchdog.check_and_alert()["alerted"] == []
        assert len(posted) == 2
        _ = job_id

    def test_local_url_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the SSRF policy blocks non-public webhook URLs."""
        monkeypatch.setattr(app_settings, "WEBHOOK_URL", "http://localhost:9/hook")
        posted = self._capture_post(monkeypatch)
        assert watchdog._webhook_url() is None
        assert posted == []
