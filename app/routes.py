"""
Route registry and router factory for the fact_inventory application.

``create_router`` builds a Litestar ``Router`` that includes all route
handlers with rate limiting already applied.  The liveness and readiness
probes are excluded from rate limiting when enabled.
"""

from typing import Any

from litestar import Router
from litestar.middleware.rate_limit import RateLimitConfig

from .settings import settings
from .unversioned import health_check, ready_check
from .v1.router import v1_router


def create_router(path: str = "/") -> Router:
    """Build a Router with all handlers and rate limiting applied.

    Parameters
    ----------
    path:
        Mount point for the router.  Defaults to ``/`` for standalone
        deployment.  Pass a prefix like ``/fact_inventory`` when
        embedding into a larger application.

    Returns
    -------
    Router
        A fully configured Litestar router.
    """
    rate_limit_excludes: list[str] = []
    route_handlers: list[Any] = []

    if settings.enable_health_endpoint:
        route_handlers.append(health_check)
        rate_limit_excludes.append("/health$")

    if settings.enable_ready_endpoint:
        route_handlers.append(ready_check)
        rate_limit_excludes.append("/ready$")

    route_handlers.append(v1_router)

    rate_limit_config = RateLimitConfig(
        rate_limit=(settings.rate_limit_unit, settings.rate_limit_max_requests),
        exclude=rate_limit_excludes,
    )

    return Router(
        path=path,
        route_handlers=route_handlers,
        middleware=[rate_limit_config.middleware],
    )
