from typing import Any, ClassVar

from litestar import Controller, Response, get
from litestar.exceptions import HTTPException
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...settings import logger


class HealthController(Controller):
    """
    Health check endpoint for container orchestrators and load balancers.
    """

    path: ClassVar[str] = "/healthz"  # type: ignore[misc]
    tags: ClassVar[list[str]] = ["health"]  # type: ignore[misc]

    @get(
        "",
        description="Liveness / readiness probe",
    )
    async def healthz(self, db_session: AsyncSession) -> Response[Any]:
        """Return 200 when the application can reach the database."""
        try:
            await db_session.execute(text("SELECT 1"))
        except Exception:
            logger.exception("Health check failed: database unreachable")
            raise HTTPException(
                detail="Database unreachable",
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
            ) from None

        return Response(
            content={"detail": "ok"},
            status_code=HTTP_200_OK,
            media_type="application/json",
        )
