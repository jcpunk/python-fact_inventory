import ipaddress
import logging

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
    Accepts test clients and supports X-Forwarded-For headers.
    """

    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        client_ip = request.headers.get("X-Forwarded-For") or request.client.host

        # Skip validation for Litestar test clients
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
