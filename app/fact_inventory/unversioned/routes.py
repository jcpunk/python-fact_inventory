"""
Unversioned operational route handlers for the fact_inventory sub-application.

These handlers are not tied to any API version and are intended for operational
use - e.g. load-balancer health checks and readiness probes.  They are defined
at relative paths (``/health``, ``/ready``) with no prefix so that the host
application controls where they are mounted via a wrapping ``Router``.
"""

import logging
from dataclasses import dataclass

from litestar import get
from litestar.exceptions import HTTPException
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.status_codes import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatusResponse:
    """Response body returned by both the liveness and readiness endpoints."""

    status: str
    service: str


@dataclass
class ErrorDetail:
    """Response body returned when an endpoint cannot satisfy the request."""

    detail: str


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
    responses={
        HTTP_200_OK: ResponseSpec(
            data_container=ServiceStatusResponse,
            description="Service is alive",
            examples=[
                Example(
                    summary="Healthy",
                    description="The application process is running normally.",
                    value={"status": "ok", "service": "fact_inventory"},
                )
            ],
        ),
    },
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
        "Returns HTTP 200 when the application can reach its required services."
        " Runs a lightweight connectivity check.  Returns HTTP 503 if a required"
        " service dependency is unreachable.  Use this as a readiness probe;"
        " use the /health endpoint as a liveness probe."
    ),
    include_in_schema=True,
    responses={
        HTTP_200_OK: ResponseSpec(
            data_container=ServiceStatusResponse,
            description="Service is ready",
            examples=[
                Example(
                    summary="Ready",
                    description="The application and all required dependencies are reachable.",
                    value={"status": "ok", "service": "fact_inventory"},
                )
            ],
        ),
        HTTP_503_SERVICE_UNAVAILABLE: ResponseSpec(
            data_container=ErrorDetail,
            description="Service Unavailable",
            examples=[
                Example(
                    summary="Service unavailable",
                    description="A required service dependency could not be reached.",
                    value={"detail": "Service unavailable"},
                )
            ],
        ),
    },
)
async def ready_check(db_session: AsyncSession) -> ServiceStatusResponse:
    """Verify service connectivity."""
    try:
        await db_session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed - dependency unreachable")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        ) from None
    return ServiceStatusResponse(status="ok", service="fact_inventory")
