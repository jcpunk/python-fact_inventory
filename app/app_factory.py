"""
Creating a Litestar application through composition with some extra features
"""

import asyncio
import contextlib
from typing import Any
from urllib.parse import urlparse

from advanced_alchemy.extensions.litestar import (
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from litestar import Litestar
from litestar.contrib.opentelemetry import OpenTelemetryConfig
from litestar.plugins.prometheus import PrometheusConfig, PrometheusController

from .fact_inventory.retention import start_retention_task
from .fact_inventory.versioned_routes import routes
from .settings import DATABASE_URI, DEBUG, RATE_LIMIT_MINUTES, logger, logging_config
from .validate_ip import validate_ip_middleware


async def _on_startup(app: Litestar) -> None:
    """Start background tasks after the application is ready."""
    task = start_retention_task()
    if task is not None:
        app.state.retention_task = task


async def _on_shutdown(app: Litestar) -> None:
    """Cancel background tasks on shutdown."""
    task: asyncio.Task[None] | None = getattr(app.state, "retention_task", None)
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> Litestar:
    """
    Application factory function to create and configure the Litestar application.

    Returns:
        Configured Litestar application instance
    """
    # ------------------------------------------------------------------
    # Database plugin setup
    # ------------------------------------------------------------------
    parsed = urlparse(DATABASE_URI)
    logger.info(
        "Configuring for database: %s://%s@%s",
        parsed.scheme,
        parsed.username,
        parsed.netloc,
    )
    alchemy_config = SQLAlchemyAsyncConfig(
        connection_string=DATABASE_URI,
        before_send_handler="autocommit",
        session_config=AsyncSessionConfig(expire_on_commit=True),
        create_all=True,  # One day you may want alembic - and to change this
    )

    # ------------------------------------------------------------------
    # Observability: Prometheus metrics + OpenTelemetry tracing
    # ------------------------------------------------------------------
    prometheus_config = PrometheusConfig(app_name="fact_inventory")
    otel_config = OpenTelemetryConfig()

    # ------------------------------------------------------------------
    # Assemble the Litestar app config
    # ------------------------------------------------------------------
    app_config: dict[str, Any] = {
        "route_handlers": [*routes, PrometheusController],
        "plugins": [SQLAlchemyPlugin(config=alchemy_config)],
        "middleware": [
            validate_ip_middleware,
            prometheus_config.middleware,
            otel_config.middleware,
        ],
        "logging_config": logging_config,
        "debug": DEBUG,
        "on_startup": [_on_startup],
        "on_shutdown": [_on_shutdown],
    }

    # ------------------------------------------------------------------
    # OpenAPI docs are enabled in debug mode
    # ------------------------------------------------------------------
    if DEBUG:
        logger.warning("OpenAPI documentation enabled (debug mode)")
    else:
        app_config["openapi_config"] = None
        logger.info("OpenAPI documentation disabled (production mode)")

    # ------------------------------------------------------------------
    # Setup the Litestar app
    # ------------------------------------------------------------------
    logger.info("Fact service starting (rate limit %s min)", RATE_LIMIT_MINUTES)
    return Litestar(**app_config)
