"""
Pytest configuration for CodeProvenance tests.
"""
import pytest
import asyncio
from typing import Generator, AsyncGenerator


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Additional test fixtures would go here
# For example: database fixtures, test clients, etc.