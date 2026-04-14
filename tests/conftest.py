"""
Pytest configuration for IntegrityDesk tests.
"""
import sys
from pathlib import Path
import pytest
import asyncio
from typing import Generator, AsyncGenerator

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Additional test fixtures would go here
# For example: database fixtures, test clients, etc.