from typing import Annotated, ClassVar

from litestar import Controller, Request, Response, post
from litestar.exceptions import HTTPException
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.params import Body
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

from ...settings import RATE_LIMIT_MINUTES, logger
from ..schemas.hostfacts import HostFacts, HostFactsWriteAPI
from .services import HostFactsService


class DetailResponse(BaseModel):  # type: ignore[misc]
    """A simple model that just has a detail string"""

    detail: str


class FactController(Controller):  # type: ignore[misc]
    """
    REST API controller for handling fact submissions.
    """

    path: ClassVar[str] = "/facts"  # URL to expose
    tags: ClassVar[list[str]] = ["v1"]  # OpenAPI Grouping of the API endpoints

    # This hard coded value is guess work
    request_max_body_size: ClassVar[int] = 1024 * 1024 * 9  # value in bytes

    @post(  # type: ignore[misc]
        "",
        dto=HostFactsWriteAPI,
        description="Submit system and package facts",
        responses={
            HTTP_201_CREATED: ResponseSpec(
                data_container=DetailResponse,
                description="Record Created",
                examples=[
                    Example(
                        summary="Resource record created",
                        description="The facts have been stored in the database."
                        " Note: this does not return a URL to review the record.",
                        value={
                            "detail": "Facts stored successfully for {client_address}"
                        },
                    )
                ],
            ),
            HTTP_400_BAD_REQUEST: ResponseSpec(
                data_container=DetailResponse,
                description="Error Code",
                examples=[
                    Example(
                        summary="Content Error",
                        description="Something went wrong parsing the payload",
                        value={"detail": "Error Message"},
                    )
                ],
            ),
            HTTP_409_CONFLICT: ResponseSpec(
                data_container=DetailResponse,
                description="Error Code",
                examples=[
                    Example(
                        summary="Database Error",
                        description="Something went wrong storing the record",
                        value={"detail": "Database error message"},
                    )
                ],
            ),
            HTTP_413_REQUEST_ENTITY_TOO_LARGE: ResponseSpec(
                data_container=DetailResponse,
                description="Error Code",
                examples=[
                    Example(
                        summary="Size Limit",
                        description="The payload is too large",
                        value={"detail": "Request Entity Too Large"},
                    )
                ],
            ),
            HTTP_429_TOO_MANY_REQUESTS: ResponseSpec(
                data_container=DetailResponse,
                description="Error Code",
                examples=[
                    Example(
                        summary="Rate Limit",
                        description="The client IP checked in too recently",
                        value={"detail": "Rate limit exceeded. Wait {delay} minutes"},
                    )
                ],
            ),
            HTTP_500_INTERNAL_SERVER_ERROR: ResponseSpec(
                data_container=DetailResponse,
                description="Error Code",
                examples=[
                    Example(
                        summary="Internal server error while processing",
                        description="Something unexpected went wrong",
                        value={"detail": "Internal server error while processing"},
                    )
                ],
            ),
        },
    )
    async def submit(
        self,
        data: Annotated[
            HostFacts,
            Body(
                examples=[
                    Example(
                        summary="RHEL Server",
                        description="Example facts from a RHEL 8.5 server",
                        value={
                            "system_facts": {
                                "os": "RHEL",
                                "version": "8.5",
                                "hostname": "server01",
                            },
                            "package_facts": {
                                "installed": ["vim", "git", "htop"],
                                "total_packages": 1247,
                            },
                        },
                    ),
                    Example(
                        summary="Minimal facts",
                        description="Minimum required data",
                        value={"system_facts": {}, "package_facts": {}},
                    ),
                ]
            ),
        ],
        request: Request,
        db_session: AsyncSession,
    ) -> Response:
        """
        Perform the actual insertion into the database.

        This includes checks for rate limits.
        Parameters are automatically checked for sanity by this point.
        """
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
                detail="Internal server error while connecting to database",
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            ) from None

        # --------------------------------------------------------------
        # Rate Limit (per IP)
        # --------------------------------------------------------------
        if await host_service.rate_limit_exceeded(client_address):
            delay = RATE_LIMIT_MINUTES + 1
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
        #   It will update or insert based on client_address
        #   If you want all historical records you could switch
        #   from `upsert` to `create` and just provide the `data` arg
        # --------------------------------------------------------------
        try:
            await host_service.upsert(
                data={
                    "client_address": client_address,
                    "system_facts": data.system_facts,
                    "package_facts": data.package_facts,
                },
                match_fields=["client_address"],  # tells it how to detect duplicates
                auto_commit=True,
            )
        except SQLAlchemyError:
            logger.exception("Database error for %s", client_address)
            raise HTTPException(
                detail="Database error: unable to store record",
                status_code=HTTP_409_CONFLICT,
            ) from None
        except Exception:
            logger.exception("Unexpected error for %s", client_address)
            raise HTTPException(
                detail="Internal server error while processing",
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            ) from None

        logger.info(
            "Stored facts for %s count - system:%d package:%d",
            client_address,
            len(data.system_facts),
            len(data.package_facts),
        )
        return Response(
            content={"detail": f"Facts stored successfully for {client_address}"},
            status_code=HTTP_201_CREATED,
            media_type="application/json",
        )
