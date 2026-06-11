"""
Pytest configuration for IntegrityDesk tests.
"""
import sys
from pathlib import Path
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient

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