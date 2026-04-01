"""
Route registry and router factory for the fact_inventory application.

``create_router`` builds a Litestar ``Router`` that includes all route
handlers with rate limiting already applied.  Health and readiness probes
are excluded from rate limiting.
"""

from litestar import Router
from litestar.middleware.rate_limit import RateLimitConfig

from .settings import settings
from .unversioned import health_check, ready_check
from .v1.controller import HostFactController as HostFactController_v1

# v1 versioned API lives under /v1.
_v1_router: Router = Router(
    path="/v1",
    route_handlers=[HostFactController_v1],
)


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
    rate_limit_config = RateLimitConfig(
        rate_limit=(settings.rate_limit_unit, settings.rate_limit_max_requests),
        exclude=["/health$", "/ready$"],
    )

    return Router(
        path=path,
        route_handlers=[health_check, ready_check, _v1_router],
        middleware=[rate_limit_config.middleware],
    )
