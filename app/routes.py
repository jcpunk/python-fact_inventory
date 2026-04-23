"""Route registry and router factory for the fact_inventory application.

:func:`create_router` assembles a :class:`~litestar.Router` that includes
all route handlers with rate limiting applied.  Liveness and readiness
probes are excluded from rate limiting and can each be suppressed
independently via the ``ENABLE_HEALTH_ENDPOINT`` and
``ENABLE_READY_ENDPOINT`` settings -- useful when embedding this
application inside a larger Litestar app that owns its own probes.
"""

from typing import Any

from litestar import Router
from litestar.middleware.rate_limit import RateLimitConfig

from .settings import settings
from .unversioned import health_check, ready_check
from .v1.router import v1_router


def create_router(path: str = "/") -> Router:
    """Return a :class:`~litestar.Router` with all handlers and rate limiting.

    Parameters
    ----------
    path:
        Mount point for the router.  Use ``"/"`` for standalone
        deployment (the default) or a prefix such as
        ``"/fact_inventory"`` when embedding in a larger application.

    Returns
    -------
    Router
        Fully assembled router ready to pass to :class:`~litestar.Litestar`.
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
        set_rate_limit_headers=True,
    )

    return Router(
        path=path,
        route_handlers=route_handlers,
        middleware=[rate_limit_config.middleware],
    )
