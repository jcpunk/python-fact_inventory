"""
Creating a Litestar application through composition with some extra features
"""

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
from litestar import Litestar, Router
from litestar.contrib.opentelemetry import OpenTelemetryConfig
from litestar.di import Provide
from litestar.openapi.config import OpenAPIConfig
from litestar.plugins.prometheus import PrometheusConfig, PrometheusController

from .fact_inventory.plugins import DailyCleanupPlugin
from .fact_inventory.routes import route_handlers as _fact_inventory_handlers
from .fact_inventory.v1.services import HostFactsService
from .settings import logger, logging_config, settings


def _get_rate_limit_minutes() -> int:
    """Provide the configured rate-limit window to fact_inventory's DI system."""
    return settings.rate_limit_minutes


def _get_retention_days() -> int:
    """Provide the configured retention window to fact_inventory's DI system."""
    return settings.retention_days


def _build_purge_fn(alchemy_config: SQLAlchemyAsyncConfig) -> Any:
    """Build an async cleanup function that purges expired host records.

    The returned coroutine creates its own short-lived database session so that
    the background task is fully independent of any request-scoped session.
    """

    async def _purge_expired_hosts() -> None:
        async with alchemy_config.get_session() as session:
            service = HostFactsService(session)
            await service.purge_expired_hosts(settings.retention_days)

    return _purge_expired_hosts


def create_app() -> Litestar:
    """
    Application factory function to create and configure the Litestar application.

    Returns:
        Configured Litestar application instance
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
    # Mount fact_inventory under the configured fact_inventory_prefix so
    # that the sub-application is completely prefix-agnostic and the host
    # app controls the URL namespace via a standard Litestar Router.
    # ------------------------------------------------------------------
    fact_inventory_router = Router(
        path=f"/{settings.fact_inventory_prefix}",
        route_handlers=_fact_inventory_handlers,
    )

    # ------------------------------------------------------------------
    # Plugins — each owns its lifecycle via InitPluginProtocol
    # ------------------------------------------------------------------
    cleanup_plugin = DailyCleanupPlugin(
        cleanup_fn=_build_purge_fn(alchemy_config),
        interval_seconds=settings.cleanup_interval_hours * 3600,
        name="host-retention-cleanup",
    )

    # ------------------------------------------------------------------
    # Assemble the Litestar app config
    # ------------------------------------------------------------------
    app_config: dict[str, Any] = {
        "route_handlers": [fact_inventory_router, PrometheusController],
        "dependencies": {
            "rate_limit_minutes": Provide(
                _get_rate_limit_minutes, sync_to_thread=False
            ),
            "retention_days": Provide(_get_retention_days, sync_to_thread=False),
        },
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
        app_config["openapi_config"] = OpenAPIConfig(
            title=settings.app_name,
            version=settings.version,
        )
        logger.warning("OpenAPI documentation enabled (debug mode)")
    else:
        app_config["openapi_config"] = None
        logger.info("OpenAPI documentation disabled (production mode)")

    # ------------------------------------------------------------------
    # Setup the Litestar app
    # ------------------------------------------------------------------
    logger.info(
        "%s version %s starting (rate limit %s min, retention %s days,"
        " cleanup every %s h)",
        settings.app_name,
        settings.version,
        settings.rate_limit_minutes,
        settings.retention_days,
        settings.cleanup_interval_hours,
    )
    return Litestar(**app_config)
