"""
Pytest configuration and fixtures for the fact_inventory test suite.
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from advanced_alchemy.extensions.litestar import (
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from litestar import Litestar
from litestar.contrib.opentelemetry import OpenTelemetryConfig
from litestar.testing import AsyncTestClient
from sqlalchemy.ext.asyncio import AsyncSession

# Set DATABASE_URI before importing app modules.
#
# pydantic-settings loads environment variables at import time, so this MUST
# be set before the app is imported below. This cannot be moved to
# pyproject.toml [tool.pytest.ini_options] because pytest does not support
# setting arbitrary environment variables in its config.
#
# For CI/CD or manual runs, you may override by setting the environment:
#   export DATABASE_URI="postgresql://..."
#   pytest
os.environ["DATABASE_URI"] = "sqlite+aiosqlite:///:memory:"

from fact_inventory.app_factory import create_app
from fact_inventory.application.services import FactInventoryService
from fact_inventory.config.background import AsyncBackgroundJobPlugin
from fact_inventory.config.settings import settings as _settings
from fact_inventory.presentation.api.router import create_router


@pytest.fixture
async def app() -> Litestar:
    """Create a Litestar app instance with an in-memory test database."""
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


@pytest.fixture
async def db_session_from_app(
    client: AsyncTestClient,
) -> AsyncGenerator[AsyncSession, None]:
    """Extract AsyncSession from app for direct DB access and state verification.

    This fixture provides a raw database session tied to the test app's
    SQLAlchemy plugin. Use this when you need to verify internal state
    directly from the database (e.g., row counts after a delete operation).

    The session is automatically closed after the test completes.

    Note: We use the client fixture to ensure the app is fully initialized
    with all tables created before yielding the session.
    """
    plugin = next(p for p in client.app.plugins if isinstance(p, SQLAlchemyPlugin))
    configs: list[SQLAlchemyAsyncConfig] = plugin._config
    async with configs[0].get_session() as session:
        yield session


@pytest.fixture
async def app_with_custom_router_path() -> Litestar:
    """Create app with router mounted at /fact_inventory prefix.

    Tests that create_router(path="/fact_inventory") integrates correctly
    with the full application stack when embedding this service in a larger app.
    """
    alchemy_config = SQLAlchemyAsyncConfig(
        connection_string="sqlite+aiosqlite:///:memory:",
        before_send_handler="autocommit",
        session_config=AsyncSessionConfig(expire_on_commit=True),
        create_all=True,
    )

    async def _cleanup_expired_facts() -> int:
        async with alchemy_config.get_session() as session:  # pragma: no cover
            service = FactInventoryService(session)
            return await service.purge_facts_older_than(_settings.retention_days)

    async def _cleanup_history_facts() -> int:
        async with alchemy_config.get_session() as session:  # pragma: no cover
            service = FactInventoryService(session)
            return await service.purge_fact_history_more_than(
                _settings.history_max_entries
            )

    retention_cleanup = AsyncBackgroundJobPlugin(
        job_callback=_cleanup_expired_facts,
        interval_seconds=_settings.retention_check_interval_hours * 3600,
        jitter_seconds=_settings.retention_check_jitter_minutes * 60,
        name="fact-inventory-retention-cleanup",
    )

    history_cleanup = AsyncBackgroundJobPlugin(
        job_callback=_cleanup_history_facts,
        interval_seconds=_settings.history_check_interval_hours * 3600,
        jitter_seconds=_settings.history_check_jitter_minutes * 60,
        name="fact-inventory-history-cleanup",
    )

    router = create_router(path="/fact_inventory")

    from fact_inventory.config.logging import get_structlog_config

    logging_cfg = get_structlog_config()

    otel_config = OpenTelemetryConfig()
    return Litestar(
        route_handlers=[router],
        plugins=[
            SQLAlchemyPlugin(config=alchemy_config),
            retention_cleanup,
            history_cleanup,
        ],
        middleware=[otel_config.middleware],
        logging_config=logging_cfg.structlog_logging_config,
        debug=_settings.debug,
        openapi_config=None,
    )


@pytest.fixture
async def client_with_custom_router_path(
    app_with_custom_router_path: Litestar,
) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide HTTP client for app with /fact_inventory router prefix."""
    async with AsyncTestClient(app=app_with_custom_router_path) as client:
        yield client


@pytest.fixture
async def app_only_health(monkeypatch: pytest.MonkeyPatch) -> Litestar:
    """Create app with only /health endpoint enabled, /ready disabled."""
    monkeypatch.setattr(_settings, "enable_ready_endpoint", False)
    return create_app()


@pytest.fixture
async def client_only_health(
    app_only_health: Litestar,
) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide HTTP client for app with only /health endpoint enabled."""
    async with AsyncTestClient(app=app_only_health) as client:
        yield client


@pytest.fixture
def valid_payload() -> dict[str, Any]:
    """Complete valid payload with all required fields."""
    return {
        "system_facts": {"os": "RHEL", "version": "9"},
        "package_facts": {"curl": "7.68.0"},
        "local_facts": {"custom_key": "custom_value"},
    }


@pytest.fixture
def minimal_payload() -> dict[str, Any]:
    """Minimal valid payload with only system_facts populated."""
    return {
        "system_facts": {"os": "RHEL"},
        "package_facts": {},
        "local_facts": {},
    }
