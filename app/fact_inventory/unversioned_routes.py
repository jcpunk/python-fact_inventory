"""
Unversioned routes for the fact_inventory application.

These routes are not tied to any API version and are intended for
operational use — e.g. load-balancer health checks and readiness probes.
The paths are rooted at /fact_inventory so the health check is clearly
scoped to this application.
"""

import logging
from dataclasses import dataclass

from litestar import Router, get
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatusResponse:
    """Response body returned by both the liveness and readiness endpoints."""

    status: str
    service: str


@get(
    "/health",
    status_code=HTTP_200_OK,
    tags=["health"],
    summary="Application liveness check",
    description=(
        "Returns HTTP 200 with a JSON body when the application process is"
        " running and able to serve requests.  This endpoint has no external"
        " dependencies (no database call) so it can be used as a fast liveness"
        " probe."
    ),
    include_in_schema=True,
)
async def health_check() -> ServiceStatusResponse:
    """Return a simple alive/ready signal for the fact_inventory service."""
    return ServiceStatusResponse(status="ok", service="fact_inventory")


@get(
    "/ready",
    status_code=HTTP_200_OK,
    tags=["health"],
    summary="Database readiness check",
    description=(
        "Returns HTTP 200 when the application can reach the database."
        " Runs a lightweight SELECT 1 query.  Returns HTTP 503 if the"
        " database is unreachable.  Use this as a readiness probe;"
        " use /fact_inventory/health as a liveness probe."
    ),
    include_in_schema=True,
)
async def ready_check(db_session: AsyncSession) -> ServiceStatusResponse:
    """Verify database connectivity with a SELECT 1 query."""
    try:
        await db_session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed — database unreachable")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
    return ServiceStatusResponse(status="ok", service="fact_inventory")


# Router rooted at /fact_inventory so full paths are:
#   /fact_inventory/health  (liveness probe)
#   /fact_inventory/ready   (readiness probe)
unversioned_router: Router = Router(
    path="/fact_inventory",
    route_handlers=[health_check, ready_check],
)

routes: list[Router] = [unversioned_router]
