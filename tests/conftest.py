"""
Pytest configuration and fixtures for the fact_inventory test suite.
"""

from collections.abc import AsyncGenerator

import pytest
from app.app_factory import create_app
from app.settings import settings as _settings
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


@pytest.fixture
async def app_no_metrics(monkeypatch: pytest.MonkeyPatch) -> Litestar:
    """Create a Litestar app with Prometheus metrics disabled."""
    monkeypatch.setattr(_settings, "enable_metrics", False)
    return create_app()


@pytest.fixture
async def client_no_metrics(
    app_no_metrics: Litestar,
) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide an async test client for an app with metrics disabled."""
    async with AsyncTestClient(app=app_no_metrics) as client:
        yield client


@pytest.fixture
async def app_no_health(monkeypatch: pytest.MonkeyPatch) -> Litestar:
    """Create a Litestar app with the /health liveness endpoint disabled."""
    monkeypatch.setattr(_settings, "enable_health_endpoint", False)
    return create_app()


@pytest.fixture
async def client_no_health(
    app_no_health: Litestar,
) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide an async test client for an app with /health disabled."""
    async with AsyncTestClient(app=app_no_health) as client:
        yield client


@pytest.fixture
async def app_no_ready(monkeypatch: pytest.MonkeyPatch) -> Litestar:
    """Create a Litestar app with the /ready readiness endpoint disabled."""
    monkeypatch.setattr(_settings, "enable_ready_endpoint", False)
    return create_app()


@pytest.fixture
async def client_no_ready(
    app_no_ready: Litestar,
) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide an async test client for an app with /ready disabled."""
    async with AsyncTestClient(app=app_no_ready) as client:
        yield client
