"""
Pytest configuration and fixtures for the fact_inventory test suite.
"""

from collections.abc import AsyncGenerator

import pytest
from app.app_factory import create_app
from litestar import Litestar
from litestar.testing import AsyncTestClient


@pytest.fixture
async def app(
    monkeypatch: pytest.MonkeyPatch,
) -> Litestar:
    """Create a Litestar app instance with an in-memory test database."""
    monkeypatch.setenv("DATABASE_URI", "sqlite+aiosqlite:///:memory:")
    return create_app()


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide an async test client for making requests."""
    async with AsyncTestClient(app=app) as client:
        yield client
