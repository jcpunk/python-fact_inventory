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
from advanced_alchemy.extensions.litestar.plugins.init.config.engine import (
    EngineConfig,
)
from litestar import Litestar
from litestar.config.cors import CORSConfig
from litestar.contrib.opentelemetry import OpenTelemetryConfig
from litestar.di import Provide
from litestar.openapi.config import OpenAPIConfig
from litestar.plugins.prometheus import PrometheusConfig, PrometheusController

from .fact_inventory.routes import routes
from .settings import (
    ALLOWED_ORIGINS,
    CREATE_ALL,
    DATABASE_URI,
    DB_POOL_MAX_OVERFLOW,
    DB_POOL_SIZE,
    DB_POOL_TIMEOUT,
    DEBUG,
    NAME,
    RATE_LIMIT_MINUTES,
    VERSION,
    logger,
    logging_config,
)
from .validate_ip import validate_ip_middleware


def _get_rate_limit_minutes() -> int:
    """Provide the configured rate-limit window to fact_inventory's DI system."""
    return RATE_LIMIT_MINUTES


async def _on_startup(app: Litestar) -> None:
    """Start background tasks after the application is ready."""
    task = None  # automatic cleanup function scheduling goes here
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

    engine_config = EngineConfig()
    if parsed.scheme and "sqlite" not in parsed.scheme:
        engine_config = EngineConfig(
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_POOL_MAX_OVERFLOW,
            pool_timeout=DB_POOL_TIMEOUT,
            pool_pre_ping=True,
        )

    alchemy_config = SQLAlchemyAsyncConfig(
        engine_config=engine_config,
        connection_string=DATABASE_URI,
        before_send_handler="autocommit",
        session_config=AsyncSessionConfig(expire_on_commit=True),
        create_all=CREATE_ALL,
    )

    # ------------------------------------------------------------------
    # CORS policy
    # ------------------------------------------------------------------
    cors_config = CORSConfig(
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    otel_config = OpenTelemetryConfig()
    prometheus_config = PrometheusConfig(app_name=NAME)

    # ------------------------------------------------------------------
    # Assemble the Litestar app config
    # ------------------------------------------------------------------
    app_config: dict[str, Any] = {
        "route_handlers": [*routes, PrometheusController],
        "dependencies": {
            "rate_limit_minutes": Provide(
                _get_rate_limit_minutes, sync_to_thread=False
            ),
        },
        "plugins": [SQLAlchemyPlugin(config=alchemy_config)],
        "middleware": [
            otel_config.middleware,
            prometheus_config.middleware,
            validate_ip_middleware,
        ],
        "on_startup": [_on_startup],
        "on_shutdown": [_on_shutdown],
        "cors_config": cors_config,
        "logging_config": logging_config,
        "debug": DEBUG,
    }

    # ------------------------------------------------------------------
    # OpenAPI docs are enabled in debug mode
    # ------------------------------------------------------------------
    if DEBUG:
        app_config["openapi_config"] = OpenAPIConfig(
            title=NAME,
            version=VERSION,
        )
        logger.warning("OpenAPI documentation enabled (debug mode)")
    else:
        app_config["openapi_config"] = None
        logger.info("OpenAPI documentation disabled (production mode)")

    # ------------------------------------------------------------------
    # Setup the Litestar app
    # ------------------------------------------------------------------
    logger.info("%s service starting (rate limit %s min)", NAME, RATE_LIMIT_MINUTES)
    return Litestar(**app_config)
