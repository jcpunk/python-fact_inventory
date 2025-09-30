"""
Creating a Litestar application through composition with some extra features
"""

from urllib.parse import urlparse

from advanced_alchemy.extensions.litestar import (
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from litestar import Litestar

from .fact_inventory.versioned_routes import routes
from .settings import DATABASE_URI, DEBUG, RATE_LIMIT_MINUTES, logger, logging_config
from .validate_ip import validate_ip_middleware


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
    # Assemble the Litestar app config
    # ------------------------------------------------------------------
    app_config = {
        "route_handlers": routes,
        "plugins": [SQLAlchemyPlugin(config=alchemy_config)],
        "middleware": [validate_ip_middleware],
        "logging_config": logging_config,
        "debug": DEBUG,
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
