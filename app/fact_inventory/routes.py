"""
Route registry for the fact_inventory application.

Call ``create_routes(prefix)`` to get all handlers - both the unversioned
operational routes (e.g. /{prefix}/health) and every versioned API router -
in a single list ready to pass to Litestar.

Usage in the application factory::

    from .fact_inventory.routes import create_routes
    app = Litestar(route_handlers=[*create_routes(prefix="fact_inventory"), ...])
"""

import logging
from dataclasses import dataclass

from litestar import Router, get
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .v1.controller import HostFactController as HostFactController_v1

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
        " use /{prefix}/health as a liveness probe."
    ),
    include_in_schema=True,
)
async def ready_check(db_session: AsyncSession) -> ServiceStatusResponse:
    """Verify database connectivity with a SELECT 1 query."""
    try:
        await db_session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed - database unreachable")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
    return ServiceStatusResponse(status="ok", service="fact_inventory")


def create_routes(prefix: str = "fact_inventory") -> list[Router]:
    """Build and return all fact_inventory route handlers under *prefix*.

    Parameters
    ----------
    prefix:
        URL path segment that scopes all routes, e.g. ``"fact_inventory"``.
        Produces paths like ``/{prefix}/health`` and ``/{prefix}/v1/facts``.
    """
    base = f"/{prefix}"
    operational_router = Router(
        path=base,
        route_handlers=[health_check, ready_check],
    )
    v1_router = Router(
        path=f"{base}/v1",
        route_handlers=[HostFactController_v1],
    )
    return [operational_router, v1_router]
