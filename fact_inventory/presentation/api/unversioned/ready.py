"""Endpoint for readiness checks.

Verifies that the database connection is healthy and the application is
ready to accept traffic. Performs a lightweight connectivity check (SELECT 1)
against the database. Unlike the liveness probe, this endpoint has external
dependencies.

Public API
----------
* ready_check - Readiness probe handler

Endpoint
--------
``GET /ready`` - Returns HTTP 200 when the application can reach its database.
Returns HTTP 503 if the database connectivity check fails.
"""

from litestar import Response, get
from litestar.exceptions import HTTPException
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.status_codes import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
            data_container=None,
            description="Service is ready",
            examples=[
                Example(
                    summary="Ready",
                    description="The application can reach its required services.",
                    value=None,
                )
            ],
        ),
        HTTP_503_SERVICE_UNAVAILABLE: ResponseSpec(
            data_container=None,
            description="Service unavailable",
            examples=[
                Example(
                    summary="Unavailable",
                    description="The application cannot reach a required service.",
                    value=None,
                )
            ],
        ),
    },
)
async def ready_check(db_session: AsyncSession) -> Response[None]:
    """Verify database connectivity for use as a Kubernetes readiness probe.

    Executes a lightweight connectivity check (SELECT 1) against the database.
    The session is managed by Litestar's dependency injection and should not
    be manually closed by the handler.

    Parameters
    ----------
    db_session : AsyncSession
        Request-scoped session injected by Litestar's SQLAlchemyPlugin.
        The session lifecycle is managed automatically and should not be
        manually closed in this handler.

    Returns
    -------
    Response[None]
        HTTP 200 with empty body.

    Raises
    ------
    HTTPException
        HTTP 503 Service Unavailable if the SELECT 1 connectivity check
        raises any exception. The original exception is logged server-side
        and suppressed from the response to avoid leaking infrastructure
        details to callers.
    """
    try:
        await db_session.execute(text("SELECT 1"))
    except Exception as err:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        ) from err
    return Response(content=None, status_code=HTTP_200_OK)
