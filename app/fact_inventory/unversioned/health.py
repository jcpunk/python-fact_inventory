"""Application liveness probe for the fact_inventory sub-application.

This handler is not tied to any API version and has no external
dependencies, making it a fast and reliable liveness check.
"""

import logging
from dataclasses import dataclass

from litestar import get
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.status_codes import HTTP_200_OK

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatusResponse:
    """Response body returned by the liveness endpoint."""

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
