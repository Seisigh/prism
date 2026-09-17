import pytest_asyncio

from server.ingest.db import close_connections


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_pool():
    """asyncpg's pool is bound to the event loop it was created on, and
    pytest-asyncio gives each test function a fresh loop — without this,
    the second test to touch the DB fails with "Event loop is closed"
    because it reuses the first test's now-dead pool."""
    yield
    await close_connections()
