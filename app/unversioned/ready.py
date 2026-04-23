"""Database readiness probe.

This handler verifies that the database connection is healthy.  It is not
tied to any API version and is intended for use as a Kubernetes-style
readiness probe.
"""

import logging

from litestar import get
from litestar.exceptions import HTTPException
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.status_codes import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .responses import ErrorDetail, ServiceStatusResponse

logger = logging.getLogger(__name__)


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
                    description=(
                        "The application and all required dependencies are reachable."
                    ),
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
    """Verify database connectivity for use as a Kubernetes readiness probe.

    Parameters
    ----------
    db_session:
        Request-scoped ``AsyncSession`` injected by Litestar's
        ``SQLAlchemyPlugin``.  The session is acquired at the start of the
        request and released automatically when the response is sent.  Do
        **not** use ``async with db_session`` here -- the session lifecycle
        is already managed by the DI framework and double-closing it will
        raise an error.  This is distinct from the cleanup plugin, which
        creates its own short-lived session via
        ``alchemy_config.get_session()``.

    Returns
    -------
    ServiceStatusResponse
        ``{"status": "ok", "service": "fact_inventory"}`` when the database
        is reachable.

    Raises
    ------
    HTTPException
        HTTP 503 Service Unavailable if the ``SELECT 1`` connectivity check
        raises any exception.  The original exception is logged server-side
        and suppressed from the response to avoid leaking infrastructure
        details to callers.
    """
    try:
        await db_session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed - dependency unreachable")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        ) from None
    return ServiceStatusResponse(status="ok", service="fact_inventory")
