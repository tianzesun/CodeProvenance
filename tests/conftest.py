"""
Pytest configuration for IntegrityDesk tests.
"""

import base64
import os
import sys
from pathlib import Path
import pytest
import asyncio
from typing import Callable, Generator, AsyncGenerator
from fastapi.testclient import TestClient

# Keep the AI detector on its fast, deterministic heuristic path during tests.
# Without this, Binoculars loads two ~500MB model checkpoints and the suite
# takes hours (and its results depend on a model download being present).
# Tests that specifically exercise Binoculars inject a fake instance instead.
os.environ.setdefault("BINOCULARS_ENABLED", "0")
# Workspace credentials are sealed at rest; tests use a throwaway key per run.
os.environ.setdefault(
    "SETTINGS_ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode()
)

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_path))


# ── Test database guard ──────────────────────────────────────────────────────
# Route, sharing and settings tests write real rows. Without this, a developer
# whose src/backend/.env.local points at the shared remote (Neon) database ran
# the suite against it. Tests now use a database on this machine unless
# ALLOW_REMOTE_TEST_DB=1 says otherwise. TEST_DATABASE_URL picks the database.
LOCAL_TEST_DATABASE_URL = "postgresql://postgres@localhost:5432/integritydesk_test"
_LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _env_file_database_url() -> str:
    """DATABASE_URL from the env file the backend would read (same rules as settings.py)."""
    if os.environ.get("APP_ENV", "development").strip().lower() == "production":
        return ""
    override = os.environ.get("APP_ENV_FILE")
    path = Path(override) if override else backend_path / ".env.local"
    if not path.is_file():
        return ""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return ""
    return (dotenv_values(path).get("DATABASE_URL") or "").strip()


def _guard_test_database() -> str:
    """Point DATABASE_URL at a local database unless remote use is allowed.

    Returns:
        A one-line description for the pytest header (host and database name,
        never the password).
    """
    from sqlalchemy.engine import make_url

    test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if test_url:
        os.environ["DATABASE_URL"] = test_url
    configured = os.environ.get("DATABASE_URL", "").strip() or _env_file_database_url()
    try:
        url = make_url(configured) if configured else None
    except Exception:
        url = None
    host = (url.host or "") if url is not None else ""
    remote = bool(host) and host not in _LOCAL_DB_HOSTS and not host.startswith("/")

    if url is None or (remote and os.environ.get("ALLOW_REMOTE_TEST_DB") != "1"):
        os.environ["DATABASE_URL"] = LOCAL_TEST_DATABASE_URL
        reason = f"remote host {host} refused" if url is not None else "no DATABASE_URL"
        return (
            f"test database: localhost/integritydesk_test ({reason}; set TEST_DATABASE_URL, "
            "or ALLOW_REMOTE_TEST_DB=1 to use a remote one)"
        )
    os.environ["DATABASE_URL"] = configured
    where = "REMOTE, allowed by ALLOW_REMOTE_TEST_DB=1" if remote else "local"
    return f"test database: {host or 'unix socket'}/{url.database} ({where})"


_TEST_DATABASE_HEADER = _guard_test_database()


def pytest_report_header(config: pytest.Config) -> str:
    """Show which database the run writes to."""
    return _TEST_DATABASE_HEADER


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _no_real_analysis_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run uploads in-process, never through a Redis that happens to be up.

    Dispatch probes the broker's port, so on a machine running Redis every
    test upload was enqueued as a real Celery task, and any local analysis
    worker then ran it. Tests that exercise Celery mode patch
    ``broker_available`` and ``delay`` themselves, which overrides this.
    """
    from src.backend.workers import dispatch

    monkeypatch.setattr(dispatch, "broker_available", lambda timeout=1.0: False)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    from src.backend.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def job_tenant_id() -> Generator[str, None, None]:
    """A workspace for tests that write jobs rows (jobs.tenant_id is required)."""
    import uuid

    from src.backend.config.database import SessionLocal
    from src.backend.models.database import Tenant

    with SessionLocal() as db:
        tenant = Tenant(
            name="Unit test workspace", api_key_hash=f"test-hash-{uuid.uuid4().hex}"
        )
        db.add(tenant)
        db.commit()
        tenant_id = str(tenant.id)
    try:
        yield tenant_id
    finally:
        with SessionLocal() as db:
            db.query(Tenant).filter(Tenant.id == tenant_id).delete()
            db.commit()


@pytest.fixture(autouse=True)
def _mutable_settings() -> Generator[None, None, None]:
    """Let tests monkeypatch fields on the otherwise-frozen settings singleton.

    ``AppSettings`` is ``frozen=True`` so production code cannot reassign a value
    after start-up. Tests legitimately need to change individual fields (feature
    flags, secrets), and the pre-existing suite does that with
    ``monkeypatch.setattr``. Unfreezing the model config here keeps those tests
    working and confines the relaxation to the test run.
    """
    from src.backend.config.settings import AppSettings, settings

    original_frozen = AppSettings.model_config.get("frozen")
    if original_frozen:
        AppSettings.model_config["frozen"] = False
    try:
        yield
    finally:
        if original_frozen:
            AppSettings.model_config["frozen"] = original_frozen


@pytest.fixture
def override_setting() -> Generator[Callable[[str, object], None], None, None]:
    """Return a helper that sets one settings field, restoring it afterwards.

    Preferred over ``monkeypatch.setattr`` when the value needs wrapping (for
    example a ``SecretStr`` field such as ``AUTH_JWT_SECRET``).
    """
    from src.backend.config.settings import settings

    original: dict[str, object] = {}

    def _override(name: str, value: object) -> None:
        """Set a settings field, remembering its previous value for restoration."""
        if name not in original:
            original[name] = getattr(settings, name)
        setattr(settings, name, value)

    yield _override

    for name, value in original.items():
        setattr(settings, name, value)
