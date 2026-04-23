"""Controller for v1 API fact submissions.

Defines the HTTP endpoint for submitting system and package facts.
Intentionally thin since it is an abstraction layer.

Controller Layer Rationale
--------------------------
Controllers translate HTTP requests into service method calls and responses.
They do not contain business logic - that lives in services. This separation
keeps endpoints stable even as rules evolve, and makes business logic testable
without mocking HTTP machinery.

JSON field size validation is performed by the service layer (domain constraint
enforcement). It appears advanced-alchemy DTOs do not support custom validators,
so size validation runs after DTO deserialization in the service layer.

Exception Strategy
------------------
All caught exceptions should use `raise HTTPException(...) from err`.

This pattern will:
- Chain the original exception so stack traces appear in server logs
- Prevent sensitive details from leaking to clients (Litestar handles that)

This ensures operators can diagnose issues while keeping responses safe
and informative.
"""

from typing import Annotated, Any

from advanced_alchemy.extensions.litestar.providers import (
    create_service_provider,
)
from litestar import Controller, Request, post
from litestar.di import Provide
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
    HTTP_504_GATEWAY_TIMEOUT,
)
from sqlalchemy.exc import SQLAlchemyError

from fact_inventory.application.exceptions import FactValidationError
from fact_inventory.application.services import FactInventoryService
from fact_inventory.config.settings import settings
from fact_inventory.infrastructure.db.models import FactInventory
from fact_inventory.presentation.api.v1.schemas.apis import FactInventoryWriteAPI
from fact_inventory.presentation.api.v1.schemas.responses import APIResponse


class FactInventoryController(Controller):
    """Controller for v1 API fact submissions.

    Rate limiting is handled externally by Litestar's RateLimitMiddleware
    (configured in the application factory). This controller is responsible
    only for HTTP boundary enforcement and persistence delegation.

    The FactInventoryService is injected via Litestar's dependency-injection
    system using advanced-alchemy's create_service_provider.
    """

    path: str = "/facts"

    # OpenAPI grouping -- Litestar reads this as an instance var,
    # so ClassVar conflicts with the base class.
    tags: list[str] = ["v1"]  # noqa: RUF012

    # Request body cap in bytes, derived from the MAX_REQUEST_BODY_MB setting.
    # See fact_inventory/config/settings.py for the rationale.
    request_max_body_size: int = settings.max_request_body_mb * 1024 * 1024

    # Service injected by advanced-alchemy's DI provider.
    dependencies: dict[str, Any] = {  # noqa: RUF012
        "fact_inventory_service": Provide(
            create_service_provider(FactInventoryService)
        ),
    }

    @post(
        "",
        dto=FactInventoryWriteAPI,
        description="Submit system and package facts",
        responses={
            HTTP_201_CREATED: ResponseSpec(
                data_container=APIResponse,
                description="Facts stored successfully",
                examples=[
                    Example(
                        summary="Record created",
                        description="The facts have been stored in the database."
                        " Note: this does not return a URL to review the record.",
                        value={
                            "status": "ok",
                            "detail": "Facts stored successfully for 192.0.2.1",
                            "data": None,
                        },
                    )
                ],
            ),
            HTTP_400_BAD_REQUEST: ResponseSpec(
                data_container=APIResponse,
                description="Bad Request -- the client address could not be determined"
                " or all fact categories are empty",
                examples=[
                    Example(
                        summary="Missing client address",
                        description=(
                            "The server could not resolve the connecting client's"
                            " IP address."
                        ),
                        value={
                            "status": "error",
                            "detail": "Validation failed",
                            "data": None,
                        },
                    ),
                    Example(
                        summary="Empty facts",
                        description="All fact categories are empty.",
                        value={
                            "status": "error",
                            "detail": "Validation failed",
                            "data": None,
                        },
                    ),
                ],
            ),
            HTTP_409_CONFLICT: ResponseSpec(
                data_container=APIResponse,
                description="Conflict -- the record could not be stored",
                examples=[
                    Example(
                        summary="Record could not be stored",
                        description="An error occurred while persisting the facts.",
                        value={
                            "status": "error",
                            "detail": "Unable to store record",
                            "data": None,
                        },
                    ),
                    Example(
                        summary="Duplicate record",
                        description=(
                            "A record with the same client address already exists."
                        ),
                        value={
                            "status": "error",
                            "detail": "Unable to store record",
                            "data": None,
                        },
                    ),
                ],
            ),
            HTTP_413_REQUEST_ENTITY_TOO_LARGE: ResponseSpec(
                data_container=APIResponse,
                description=(
                    "Payload Too Large -- the request body exceeds the configured"
                    " size limit"
                ),
                examples=[
                    Example(
                        summary="Body too large",
                        description=(
                            "The submitted payload exceeds the maximum allowed size."
                        ),
                        value={
                            "status": "error",
                            "detail": "Validation failed",
                            "data": None,
                        },
                    ),
                    Example(
                        summary="JSON field too large",
                        description=(
                            "A JSON field in the request exceeds the "
                            "configured size limit."
                        ),
                        value={
                            "status": "error",
                            "detail": "Validation failed",
                            "data": None,
                        },
                    ),
                ],
            ),
            HTTP_429_TOO_MANY_REQUESTS: ResponseSpec(
                data_container=APIResponse,
                description=(
                    "Too Many Requests -- the client has exceeded the rate limit."
                    " Check the RateLimit-* response headers."
                ),
                examples=[
                    Example(
                        summary="Rate limit exceeded",
                        description=(
                            "The client must wait before submitting again."
                            " Handled automatically by litestar.middleware.rate_limit."
                        ),
                        value={
                            "status": "error",
                            "detail": "Validation failed",
                            "data": None,
                        },
                    ),
                    Example(
                        summary="Rate limit exceeded with retry time",
                        description=(
                            "The client has exceeded the rate limit and must wait"
                            " for the specified time before retrying."
                        ),
                        value={
                            "status": "error",
                            "detail": "Validation failed",
                            "data": {"retry_after": 60},
                        },
                    ),
                ],
            ),
            HTTP_500_INTERNAL_SERVER_ERROR: ResponseSpec(
                data_container=APIResponse,
                description="Internal Server Error -- an unexpected error occurred",
                examples=[
                    Example(
                        summary="Unexpected server error",
                        description=(
                            "An unexpected error occurred; details are recorded"
                            " server-side."
                        ),
                        value={
                            "status": "error",
                            "detail": "Internal server error",
                            "data": None,
                        },
                    ),
                    Example(
                        summary="Unexpected error with context",
                        description=(
                            "An unexpected error occurred during fact processing."
                        ),
                        value={
                            "status": "error",
                            "detail": "Internal server error",
                            "data": {"error_type": "FactValidationError"},
                        },
                    ),
                ],
            ),
            HTTP_504_GATEWAY_TIMEOUT: ResponseSpec(
                data_container=APIResponse,
                description="Gateway Timeout -- an upstream operation timed out",
                examples=[
                    Example(
                        summary="Database timeout",
                        description=(
                            "The database operation exceeded the configured timeout."
                        ),
                        value={
                            "status": "error",
                            "detail": "Request timeout",
                            "data": None,
                        },
                    ),
                    Example(
                        summary="Operation timeout with context",
                        description=(
                            "An upstream service or database operation timed out."
                        ),
                        value={
                            "status": "error",
                            "detail": "Request timeout",
                            "data": {"operation": "database_write"},
                        },
                    ),
                ],
            ),
        },
    )
    async def submit(
        self,
        data: Annotated[
            FactInventory,
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
                            },
                            "local_facts": {"key": "value"},
                        },
                    ),
                    Example(
                        summary="Minimal facts",
                        description="Minimum required data with all fact categories",
                        value={
                            "system_facts": {},
                            "package_facts": {},
                            "local_facts": {},
                        },
                    ),
                ]
            ),
        ],
        request: Request[Any, Any, Any],
        fact_inventory_service: FactInventoryService,
    ) -> APIResponse:
        """Store submitted system and package facts for the calling client.

        The calling client is identified by its IP address (from
        request.client.host). If a record for that IP exists it is
        updated; otherwise a new record is created.

        Request validation is delegated to the DTO layer (FactInventoryWriteAPI)
        for field exclusion and unknown field rejection. JSON field size
        validation is performed by the service layer and raises ValueError if
        limits are exceeded; the controller converts this to HTTP 413.
        Rate limiting is enforced by the middleware before this handler runs.
        Persistence is delegated to the injected service.

        Rate Limiting
        -------------
        This endpoint is rate-limited according to the ``RATE_LIMIT_MAX_REQUESTS``
        and ``RATE_LIMIT_UNIT`` settings. When the rate limit is exceeded, the
        server returns HTTP 429 Too Many Requests. The response includes
        RateLimit-Limit, RateLimit-Remaining, and RateLimit-Reset headers to
        inform clients of their quota status.

        Parameters
        ----------
        data : FactInventory
            The validated fact inventory data from the request body.
        request : Request
            The HTTP request object used to extract the client IP address.
        fact_inventory_service : FactInventoryService
            The service instance injected by Litestar's dependency system.

        Returns
        -------
        APIResponse
            HTTP 201 Created with APIResponse envelope on success.

        Raises
        ------
        HTTPException
            HTTP 400 if client address cannot be determined or facts are empty.
        HTTPException
            HTTP 413 if any JSON field exceeds the configured size limit.
        HTTPException
            HTTP 409 if database persistence fails.
        HTTPException
            HTTP 500 for unexpected errors.
        """
        if request.client is None:  # pragma: no cover
            request.logger.warning("Unable to determine client address")
            raise HTTPException(
                detail="Unable to determine client address",
                status_code=HTTP_400_BAD_REQUEST,
            )
        client_address = request.client.host

        try:
            await fact_inventory_service.upsert_client_record(
                data={
                    "client_address": client_address,
                    "system_facts": data.system_facts,
                    "package_facts": data.package_facts,
                    "local_facts": data.local_facts,
                }
            )
        except HTTPException:
            raise
        except FactValidationError as err:
            await self._handle_error(err, client_address, request, HTTP_400_BAD_REQUEST)
        except SQLAlchemyError as err:
            await self._handle_error(err, client_address, request, HTTP_409_CONFLICT)
        except ValueError as err:
            await self._handle_error(
                err, client_address, request, HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )
        except TimeoutError as err:
            await self._handle_error(
                err, client_address, request, HTTP_504_GATEWAY_TIMEOUT
            )
        except Exception as err:
            await self._handle_error(
                err, client_address, request, HTTP_500_INTERNAL_SERVER_ERROR
            )

        await self._log_record_created(client_address, request)
        return APIResponse(
            status="ok",
            detail=f"Facts stored successfully for {client_address}",
            data=None,
        )

    @staticmethod
    async def _handle_error(
        err: Exception,
        client_address: str,
        request: Request[Any, Any, Any],
        status_code: int,
    ) -> None:
        """Handle exceptions and convert them to HTTP responses.

        Maps exceptions to appropriate HTTP status codes and logs the error
        with client context for debugging.

        Parameters
        ----------
        err : Exception
            The exception that was raised.
        client_address : str
            The client IP address for logging context.
        request : Request
            The HTTP request object for logging.
        status_code : int
            The HTTP status code to return to the client.

        Raises
        ------
        HTTPException
            Always raised with appropriate status code and detail message.
        """
        if status_code == HTTP_400_BAD_REQUEST:
            request.logger.warning(
                "Error for client",
                client_address=client_address,
            )
            raise HTTPException(
                detail="Validation failed", status_code=status_code
            ) from err
        if status_code == HTTP_409_CONFLICT:
            request.logger.error(
                "Error for client",
                client_address=client_address,
            )
            raise HTTPException(
                detail="Unable to store record", status_code=status_code
            ) from err
        if status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            request.logger.warning(
                "Error for client",
                client_address=client_address,
            )
            raise HTTPException(
                detail="Validation failed", status_code=status_code
            ) from err
        if status_code == HTTP_504_GATEWAY_TIMEOUT:
            request.logger.error(
                "Error for client",
                client_address=client_address,
            )
            raise HTTPException(
                detail="Request timeout", status_code=status_code
            ) from err
        request.logger.critical(
            "Error for client",
            client_address=client_address,
        )
        raise HTTPException(
            detail="Internal server error", status_code=status_code
        ) from err

    @staticmethod
    async def _log_record_created(
        client_address: str,
        request: Request[Any, Any, Any],
    ) -> None:
        """Log successful record creation with request context.

        Parameters
        ----------
        client_address : str
            The client IP address that submitted the facts.
        request : Request
            The HTTP request object for logging context.
        """
        request.logger.info(
            "Fact inventory record created",
            http_request_method="POST",
            http_response_status_code=201,
            http_route="/api/v1/facts",
            client_address=client_address,
        )
