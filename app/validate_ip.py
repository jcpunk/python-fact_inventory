import ipaddress
import logging
from typing import Any

from litestar import Request
from litestar.exceptions import HTTPException
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
)
from litestar.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


def validate_ip_middleware(app: ASGIApp) -> ASGIApp:
    """
    Middleware to validate client IP addresses for all incoming requests.
    Also accepts `testclient`
    """

    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        request: Request[Any, Any, Any] = Request(scope, receive, send)

        if request.client is None:
            raise HTTPException(
                detail="Unable to determine client address",
                status_code=HTTP_400_BAD_REQUEST,
            )

        client_ip = request.client.host

        # Skip validation for Litestar test clients
        # PostgreSQL servers using the INET column type will error out on `testclient`
        # TODO: find a way to make this work whenever
        if client_ip == "testclient":
            logger.debug("Test client detected, skipping IP validation")
            await app(scope, receive, send)
            return

        try:
            ipaddress.ip_address(client_ip)
        except ValueError:
            logger.exception(
                "Invalid client IP %s for request %s %s",
                client_ip,
                request.method,
                request.url.path,
            )
            raise HTTPException(
                detail=f"Invalid client IP: {client_ip}",
                status_code=HTTP_400_BAD_REQUEST,
            ) from None

        await app(scope, receive, send)

    return middleware
