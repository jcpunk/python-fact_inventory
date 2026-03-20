import logging
from typing import Annotated, Any

from litestar import Controller, Request, Response, post
from litestar.exceptions import HTTPException
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.params import Body, Dependency
from litestar.status_codes import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_409_CONFLICT,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import MAX_REQUEST_BODY_BYTES
from ..schemas.hostfacts import HostFacts, HostFactsWriteAPI
from .services import HostFactsService

logger = logging.getLogger(__name__)


class DetailResponse(BaseModel):
    """Response envelope returned on both success and error paths."""

    detail: str


# ---------------------------------------------------------------------------
# OpenAPI response specs for HostFactController.submit
# Kept as module-level dicts so that success and error cases are clearly
# separated and each entry can carry a precise, actionable description.
# ---------------------------------------------------------------------------

_SUBMIT_SUCCESS_RESPONSES: dict = {
    HTTP_201_CREATED: ResponseSpec(
        data_container=DetailResponse,
        description="Facts stored successfully",
        examples=[
            Example(
                summary="Record created",
                description="The facts have been stored in the database."
                " Note: this does not return a URL to review the record.",
                value={"detail": "Facts stored successfully for 192.0.2.1"},
            )
        ],
    ),
}

_SUBMIT_ERROR_RESPONSES: dict = {
    HTTP_400_BAD_REQUEST: ResponseSpec(
        data_container=DetailResponse,
        description="Bad Request — the client address could not be determined",
        examples=[
            Example(
                summary="Missing client address",
                description="The server could not resolve the connecting client's IP address.",
                value={"detail": "Unable to determine client address"},
            )
        ],
    ),
    HTTP_409_CONFLICT: ResponseSpec(
        data_container=DetailResponse,
        description="Conflict — the record could not be stored",
        examples=[
            Example(
                summary="Record could not be stored",
                description="An error occurred while persisting the facts.",
                value={"detail": "Unable to store record"},
            )
        ],
    ),
    HTTP_413_REQUEST_ENTITY_TOO_LARGE: ResponseSpec(
        data_container=DetailResponse,
        description="Payload Too Large — the request body exceeds the configured size limit",
        examples=[
            Example(
                summary="Body too large",
                description="The submitted payload exceeds the maximum allowed size.",
                value={"detail": "Request Entity Too Large"},
            )
        ],
    ),
    HTTP_429_TOO_MANY_REQUESTS: ResponseSpec(
        data_container=DetailResponse,
        description="Too Many Requests — this client IP submitted facts too recently",
        examples=[
            Example(
                summary="Rate limit exceeded",
                description="The client must wait before submitting again."
                " Check the Retry-After response header for the exact delay.",
                value={"detail": "Rate limit exceeded. Wait 28 minutes"},
            )
        ],
    ),
    HTTP_500_INTERNAL_SERVER_ERROR: ResponseSpec(
        data_container=DetailResponse,
        description="Internal Server Error — an unexpected error occurred",
        examples=[
            Example(
                summary="Unexpected server error",
                description="An unexpected error occurred; details are recorded server-side.",
                value={"detail": "Internal server error"},
            )
        ],
    ),
}


class HostFactController(Controller):
    """
    REST API controller for handling fact submissions.
    """

    # URL to expose
    path: str = "/facts"

    # OpenAPI Grouping of the API endpoints
    # Litestar reads this as an instance var
    # thus ClassVar conflicts with base class, disable RUF012
    tags: list[str] = ["v1"]  # noqa: RUF012

    # See app/fact_inventory/constants.py for the rationale behind this value.
    request_max_body_size: int = MAX_REQUEST_BODY_BYTES

    @post(
        "",
        dto=HostFactsWriteAPI,
        description="Submit system and package facts",
        responses={**_SUBMIT_SUCCESS_RESPONSES, **_SUBMIT_ERROR_RESPONSES},
    )
    async def submit(
        self,
        data: Annotated[
            HostFacts,
            Body(
                examples=[
                    Example(
                        summary="Fedora System",
                        description="Example facts from a Fedora 42 installation",
                        value={
                            "system_facts": {
                                "distribution": "Fedora",
                                "distribution_file_path": "/etc/redhat-release",
                                "distribution_file_variety": "RedHat",
                                "distribution_major_version": "42",
                                "distribution_version": "42",
                            },
                            "package_facts": {
                                "glibc": [
                                    {
                                        "arch": "x86_64",
                                        "epoch": "null",
                                        "name": "glibc",
                                        "release": "11.fc42",
                                        "source": "rpm",
                                        "version": "2.41",
                                    }
                                ],
                                "glibc-common": [
                                    {
                                        "arch": "x86_64",
                                        "epoch": "null",
                                        "name": "glibc-common",
                                        "release": "11.fc42",
                                        "source": "rpm",
                                        "version": "2.41",
                                    }
                                ],
                            },
                        },
                    ),
                    Example(
                        summary="Minimal facts",
                        description="Minimum required data, technically none",
                        value={"system_facts": {}, "package_facts": {}},
                    ),
                ]
            ),
        ],
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        # Default 27 is the standalone fallback; host apps override via Provide.
        rate_limit_minutes: Annotated[int, Dependency()] = 27,
    ) -> Response[Any]:
        """
        Perform the actual insertion into the database.

        This includes checks for rate limits.

        Parameters are automatically checked for sanity by this point.
        """
        if request.client is None:
            raise HTTPException(
                detail="Unable to determine client address",
                status_code=HTTP_400_BAD_REQUEST,
            )
        client_address = request.client.host
        logger.info("Facts submission from %s", client_address)

        # --------------------------------------------------------------
        # Setup database connection scoped to HostFacts
        # --------------------------------------------------------------
        try:
            host_service = HostFactsService(db_session)
        except Exception:
            logger.exception(
                "Unexpected error generating session for %s", client_address
            )
            raise HTTPException(
                detail="Internal server error",
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            ) from None

        # --------------------------------------------------------------
        # Rate Limit (per IP)
        # --------------------------------------------------------------
        if await host_service.rate_limit_exceeded(client_address, rate_limit_minutes):
            delay = rate_limit_minutes + 1
            logger.warning("Rate limit hit for %s", client_address)

            # Always back off a full minute beyond the rate limit window.
            # Even if the caller has close to being granted access, we
            # intentionally extend the pause so the server does not need
            # to compute a precise remaining time value for clients.
            raise HTTPException(
                detail=f"Rate limit exceeded. Wait {delay} minutes",
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(delay * 60)},
            )

        # --------------------------------------------------------------
        # Store the facts in the database
        # --------------------------------------------------------------
        try:
            await host_service.save_client(
                data={
                    "client_address": client_address,
                    "system_facts": data.system_facts,
                    "package_facts": data.package_facts,
                }
            )
        except SQLAlchemyError:
            logger.exception("Database error for %s", client_address)
            raise HTTPException(
                detail="Unable to store record",
                status_code=HTTP_409_CONFLICT,
            ) from None
        except Exception:
            logger.exception("Unexpected error for %s", client_address)
            raise HTTPException(
                detail="Internal server error",
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            ) from None

        logger.info(
            "Stored facts for client %s - fact count system:%d package:%d",
            client_address,
            len(data.system_facts),
            len(data.package_facts),
        )
        return Response(
            content={"detail": f"Facts stored successfully for {client_address}"},
            status_code=HTTP_201_CREATED,
            media_type="application/json",
        )
