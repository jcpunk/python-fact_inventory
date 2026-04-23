"""Application factory pattern implementation for the Litestar ASGI application.

The factory pattern wires together:

- Database via SQLAlchemy async using ``advanced_alchemy``.
- Observability via OpenTelemetry and Prometheus.
- Rate limiting baked into the router via ``create_router``.
- Background job scheduler via ``AsyncBackgroundJobPlugin``.
- All route handlers.

All configuration tunables are read from the ``settings`` singleton
(see fact_inventory/config/settings.py).
"""

import logging
from typing import Any
from urllib.parse import urlparse

from advanced_alchemy.extensions.litestar import (
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from advanced_alchemy.extensions.litestar.plugins.init.config.engine import (
    EngineConfig,
)
from litestar import Litestar
from litestar.config.compression import CompressionConfig
from litestar.contrib.opentelemetry import OpenTelemetryConfig, OpenTelemetryPlugin
from litestar.openapi.config import OpenAPIConfig
from litestar.plugins.prometheus import PrometheusConfig, PrometheusController
from litestar.plugins.structlog import StructlogPlugin

from fact_inventory.application.services import FactInventoryService
from fact_inventory.config.background import AsyncBackgroundJobPlugin
from fact_inventory.config.logging import get_structlog_config
from fact_inventory.config.settings import settings
from fact_inventory.presentation.api.router import create_router

__all__ = ["create_app"]


def create_app() -> Litestar:
    """Assemble and return a fully configured Litestar ASGI application.

    The application factory pattern wires together the database plugin,
    background cleanup tasks, observability middleware (Prometheus
    optional), and rate-limited route handlers.
    All configuration tunables are read from the settings singleton.

    OpenAPI documentation is enabled only when DEBUG=true to avoid
    exposing the schema on production deployments.

    Returns
    -------
    Litestar
        Fully configured Litestar application ready to be served by
        an ASGI server such as Uvicorn.
    """

    # Database plugin setup
    parsed = urlparse(settings.database_uri)

    engine_config = EngineConfig(echo=settings.debug)
    if parsed.scheme and "sqlite" not in parsed.scheme:
        engine_config = EngineConfig(  # pragma: no cover
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_pool_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,
            echo=settings.debug,
        )

    alchemy_config = SQLAlchemyAsyncConfig(
        engine_config=engine_config,
        connection_string=settings.database_uri,
        before_send_handler="autocommit",
        session_config=AsyncSessionConfig(expire_on_commit=True),
        create_all=settings.create_all,
    )

    # Background job scheduler - retention cleanup
    async def _cleanup_expired_facts() -> int:
        """Delete facts older than the configured retention window.

        Parameters
        ----------
        None

        Returns
        -------
        int
            Number of records deleted.
        """
        async with alchemy_config.get_session() as session:
            service = FactInventoryService(session)
            return await service.purge_facts_older_than(settings.retention_days)

    retention_cleanup_plugin = AsyncBackgroundJobPlugin(
        job_callback=_cleanup_expired_facts,
        interval_seconds=settings.retention_check_interval_hours * 3600,
        jitter_seconds=settings.retention_check_jitter_minutes * 60,
        name="fact-inventory-retention-cleanup",
    )

    # Background job scheduler - history cleanup
    async def _cleanup_fact_history() -> int:
        """Delete fact history records per client_address exceeding max_entries.

        Parameters
        ----------
        None

        Returns
        -------
        int
            Number of records deleted.
        """
        async with alchemy_config.get_session() as session:
            service = FactInventoryService(session)
            return await service.purge_fact_history_more_than(
                settings.history_max_entries
            )

    history_cleanup_plugin = AsyncBackgroundJobPlugin(
        job_callback=_cleanup_fact_history,
        interval_seconds=settings.history_check_interval_hours * 3600,
        jitter_seconds=settings.history_check_jitter_minutes * 60,
        name="fact-inventory-history-cleanup",
    )

    # Logging configuration - structlog with OTEL compliance
    logging_cfg = get_structlog_config()

    # Assemble the Litestar app
    app_kwargs: dict[str, Any] = {
        "route_handlers": [create_router()],
        "plugins": [
            SQLAlchemyPlugin(config=alchemy_config),
            OpenTelemetryPlugin(OpenTelemetryConfig()),
            StructlogPlugin(config=logging_cfg),
        ],
        "middleware": [],
        "compression_config": CompressionConfig(
            backend="gzip",
        ),
        "logging_config": logging_cfg.structlog_logging_config,
        "openapi_config": None,
        "debug": settings.debug,
    }

    if settings.debug:
        app_kwargs["openapi_config"] = OpenAPIConfig(
            title=settings.app_name,
            version=settings.version,
        )

    if settings.enable_retention_cleanup_job:
        app_kwargs["plugins"].append(retention_cleanup_plugin)

    if settings.enable_history_cleanup_job:
        app_kwargs["plugins"].append(history_cleanup_plugin)

    if settings.enable_metrics:
        prometheus_config = PrometheusConfig(app_name=settings.app_name)
        app_kwargs["route_handlers"].append(PrometheusController)
        app_kwargs["middleware"].append(prometheus_config.middleware)

    logging.getLogger(__name__).info("Fact Inventory application starting")

    return Litestar(**app_kwargs)
