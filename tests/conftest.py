"""
Pytest configuration for IntegrityDesk tests.
"""

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

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    from src.backend.main import app

    with TestClient(app) as test_client:
        yield test_client


# Additional test fixtures would go here
# For example: database fixtures, test clients, etc.


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
        object.__setattr__(settings, name, value)

    yield _override

    for name, value in original.items():
        object.__setattr__(settings, name, value)
