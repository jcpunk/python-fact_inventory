"""Route registry and router factory for the fact_inventory application.

create_router assembles a Router that includes all route handlers with
rate limiting applied. Liveness and readiness probes are excluded from
rate limiting and can each be suppressed independently via the
ENABLE_HEALTH_ENDPOINT and ENABLE_READY_ENDPOINT settings (useful when
embedding this application inside a larger Litestar app that owns its
own probes).

Notes
-----
All versioned endpoints are rate-limited to the configured limit (default:
2 requests per hour). Health and readiness probes are excluded from rate
limiting to allow infrastructure monitoring to function without interference.

Examples
--------
>>> router = create_router()
>>> app = Litestar(route_handlers=[router])
>>> router = create_router(path="/fact_inventory")
>>> app = Litestar(route_handlers=[router])
"""

from typing import Any

from litestar import Router
from litestar.middleware.rate_limit import RateLimitConfig

from fact_inventory.config.settings import settings
from fact_inventory.presentation.api.unversioned.health import health_check
from fact_inventory.presentation.api.unversioned.ready import ready_check
from fact_inventory.presentation.api.v1.router import v1_router

__all__ = ["create_router"]


def create_router(path: str = "/") -> Router:
    """Return a Router with all handlers and rate limiting applied.

    The returned router includes all versioned endpoints with rate limiting.
    Health and readiness probes are excluded from rate limiting by default
    and can be independently enabled or disabled via configuration.

    Parameters
    ----------
    path : str
        Mount point for the router. Use "/" for standalone deployment
        (the default) or a prefix such as "/fact_inventory" when
        embedding in a larger application.

    Returns
    -------
    Router
        Fully assembled router ready to pass to Litestar.
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
        set_rate_limit_headers=settings.debug,
    )

    return Router(
        path=path,
        route_handlers=route_handlers,
        middleware=[rate_limit_config.middleware],
    )
