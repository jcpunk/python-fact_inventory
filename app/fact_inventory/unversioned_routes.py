"""
Unversioned routes for the fact_inventory application.

These routes are not tied to any API version and are intended for
operational use — e.g. load-balancer health checks and readiness probes.
The paths are rooted at /fact_inventory so the health check is clearly
scoped to this application.
"""

from __future__ import annotations

from dataclasses import dataclass

from litestar import Router, get
from litestar.status_codes import HTTP_200_OK


@dataclass
class HealthResponse:
    """Response body returned by the health check endpoint."""

    status: str
    service: str


@get(
    "/health",
    status_code=HTTP_200_OK,
    tags=["health"],
    summary="Application health check",
    description=(
        "Returns HTTP 200 with a JSON body when the application process is"
        " running and able to serve requests.  This endpoint has no external"
        " dependencies (no database call) so it can be used as a fast liveness"
        " probe."
    ),
    include_in_schema=True,
)
async def health_check() -> HealthResponse:
    """Return a simple alive/ready signal for the fact_inventory service."""
    return HealthResponse(status="ok", service="fact_inventory")


# Router rooted at /fact_inventory so the full path is /fact_inventory/health
unversioned_router: Router = Router(
    path="/fact_inventory",
    route_handlers=[health_check],
)

routes: list[Router] = [unversioned_router]
