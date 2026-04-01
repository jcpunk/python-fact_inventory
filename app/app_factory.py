"""
Application factory -- creates and configures the Litestar ASGI application.

The factory wires together:
* Database (SQLAlchemy async via ``advanced_alchemy``)
* Observability (OpenTelemetry + Prometheus)
* Rate limiting (baked into the router via ``create_router``)
* Background retention cleanup (``DailyCleanupPlugin``)
* All route handlers

All tunables are read from the ``settings`` singleton (see ``settings.py``).
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
from litestar.contrib.opentelemetry import OpenTelemetryConfig
from litestar.openapi.config import OpenAPIConfig
from litestar.plugins.prometheus import PrometheusConfig, PrometheusController

from .cleanup import DailyCleanupPlugin
from .routes import create_router
from .settings import logging_config, settings
from .v1.services import HostFactsService

logger = logging.getLogger(__name__)


def create_app() -> Litestar:
    """Create and return a fully configured Litestar application.

    Returns
    -------
    Litestar
        The application instance ready to be served by an ASGI server.
    """
    # ------------------------------------------------------------------
    # Database plugin setup
    # ------------------------------------------------------------------
    parsed = urlparse(settings.database_uri)
    logger.info(
        "Configuring for database: %s://%s@%s",
        parsed.scheme,
        parsed.username,
        parsed.netloc,
    )

    engine_config = EngineConfig()
    if parsed.scheme and "sqlite" not in parsed.scheme:
        engine_config = EngineConfig(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_pool_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,
        )

    alchemy_config = SQLAlchemyAsyncConfig(
        engine_config=engine_config,
        connection_string=settings.database_uri,
        before_send_handler="autocommit",
        session_config=AsyncSessionConfig(expire_on_commit=True),
        create_all=settings.create_all,
    )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    otel_config = OpenTelemetryConfig()
    prometheus_config = PrometheusConfig(app_name=settings.app_name)

    # ------------------------------------------------------------------
    # Background retention cleanup
    # ------------------------------------------------------------------
    async def _purge_expired_hosts() -> None:
        """Purge host records older than the configured retention window.

        Creates its own short-lived database session so the background
        task is fully independent of any request-scoped session.
        """
        async with alchemy_config.get_session() as session:
            service = HostFactsService(session)
            await service.purge_expired_hosts(settings.retention_days)

    cleanup_plugin = DailyCleanupPlugin(
        cleanup_fn=_purge_expired_hosts,
        interval_seconds=settings.cleanup_interval_hours * 3600,
        jitter_seconds=settings.cleanup_jitter_minutes * 60,
        name="host-retention-cleanup",
    )

    # ------------------------------------------------------------------
    # Assemble the Litestar app
    # ------------------------------------------------------------------
    app_kwargs: dict[str, Any] = {
        "route_handlers": [create_router(), PrometheusController],
        "plugins": [SQLAlchemyPlugin(config=alchemy_config), cleanup_plugin],
        "middleware": [
            otel_config.middleware,
            prometheus_config.middleware,
        ],
        "logging_config": logging_config,
        "debug": settings.debug,
    }

    # ------------------------------------------------------------------
    # OpenAPI docs are ONLY enabled in debug mode
    # ------------------------------------------------------------------
    if settings.debug:
        app_kwargs["openapi_config"] = OpenAPIConfig(
            title=settings.app_name,
            version=settings.version,
        )
        logger.warning("OpenAPI documentation enabled (debug mode)")
    else:
        app_kwargs["openapi_config"] = None
        logger.info("OpenAPI documentation disabled (production mode)")

    # ------------------------------------------------------------------
    # Log the final configuration and return the app
    # ------------------------------------------------------------------
    logger.info(
        "%s version %s starting"
        " (rate limit %s req/%s, retention %s days,"
        " cleanup every %s h, jitter up to %s min)",
        settings.app_name,
        settings.version,
        settings.rate_limit_max_requests,
        settings.rate_limit_unit,
        settings.retention_days,
        settings.cleanup_interval_hours,
        settings.cleanup_jitter_minutes,
    )
    return Litestar(**app_kwargs)
