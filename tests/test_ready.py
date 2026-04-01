"""
Tests for the unversioned /ready endpoint.
"""

from unittest.mock import AsyncMock, patch

from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from litestar.testing import AsyncTestClient


class TestReadinessCheck:
    """Tests for GET /ready."""

    async def test_ready_returns_ok(self, client: AsyncTestClient) -> None:
        """The readiness endpoint must respond with HTTP 200 when the DB is up."""
        response = await client.get("/ready")
        assert response.status_code == HTTP_200_OK

    async def test_ready_body_status(self, client: AsyncTestClient) -> None:
        """Response body must contain status 'ok'."""
        response = await client.get("/ready")
        assert response.json()["status"] == "ok"

    async def test_ready_body_service(self, client: AsyncTestClient) -> None:
        """Response body must identify the service as 'fact_inventory'."""
        response = await client.get("/ready")
        assert response.json()["service"] == "fact_inventory"

    async def test_ready_content_type(self, client: AsyncTestClient) -> None:
        """Response must be JSON."""
        response = await client.get("/ready")
        assert "application/json" in response.headers["content-type"]

    async def test_ready_no_extra_fields(self, client: AsyncTestClient) -> None:
        """Response body must contain exactly the documented fields."""
        response = await client.get("/ready")
        assert set(response.json().keys()) == {"status", "service"}

    async def test_ready_post_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; POST must be rejected."""
        response = await client.post("/ready", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_ready_put_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; PUT must be rejected."""
        response = await client.put("/ready", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_ready_delete_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; DELETE must be rejected."""
        response = await client.delete("/ready")
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_ready_db_failure_returns_503(
        self,
        client: AsyncTestClient,
    ) -> None:
        """When the database is unreachable, the endpoint must return HTTP 503."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            response = await client.get("/ready")
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE

    async def test_ready_db_failure_body(self, client: AsyncTestClient) -> None:
        """When the database is unreachable, the response body must contain a detail."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            response = await client.get("/ready")
        assert "detail" in response.json()

    async def test_ready_db_failure_detail_is_safe(
        self, client: AsyncTestClient
    ) -> None:
        """503 response must not reveal internal implementation details."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            response = await client.get("/ready")
        detail = response.json()["detail"].lower()
        assert "database" not in detail
        assert "sql" not in detail
        assert "select" not in detail

    async def test_ready_patch_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; PATCH must be rejected."""
        response = await client.patch("/ready")
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_ready_503_content_type_is_json(
        self, client: AsyncTestClient
    ) -> None:
        """503 response must be JSON, not plain text or HTML."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            response = await client.get("/ready")
        assert "application/json" in response.headers["content-type"]

    async def test_ready_503_has_only_detail_key(self, client: AsyncTestClient) -> None:
        """503 body must contain standard Litestar error keys only."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            response = await client.get("/ready")
        assert set(response.json().keys()) == {"detail", "status_code"}

    async def test_ready_original_exception_not_leaked(
        self, client: AsyncTestClient
    ) -> None:
        """The original exception message must not appear in the 503 response."""
        some_message = "internal_error_xyz"
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception(some_message),
        ):
            response = await client.get("/ready")
        assert some_message not in response.text

    async def test_ready_repeated_calls_consistent(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Multiple successive calls must all return the same response."""
        for _ in range(3):
            response = await client.get("/ready")
            assert response.status_code == HTTP_200_OK
            assert response.json() == {"status": "ok", "service": "fact_inventory"}

    async def test_ready_is_distinct_from_health(
        self,
        client: AsyncTestClient,
    ) -> None:
        """The readiness probe lives at a different path than the liveness probe."""
        health = await client.get("/health")
        ready = await client.get("/ready")
        assert health.status_code == HTTP_200_OK
        assert ready.status_code == HTTP_200_OK

    async def test_health_still_ok_when_db_down(
        self,
        client: AsyncTestClient,
    ) -> None:
        """The liveness probe must return 200 even when the DB is unreachable."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            ready = await client.get("/ready")
            health = await client.get("/health")
        assert ready.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert health.status_code == HTTP_200_OK

    async def test_ready_not_rate_limited(self, client: AsyncTestClient) -> None:
        """Readiness probe must never be throttled by the rate limiter."""
        for _ in range(5):
            response = await client.get("/ready")
            assert response.status_code == HTTP_200_OK


class TestReadyEndpointDisabled:
    """Tests for /ready when ENABLE_READY_ENDPOINT=false."""

    async def test_ready_returns_404_when_disabled(
        self, client_no_ready: AsyncTestClient
    ) -> None:
        """When the readiness endpoint is disabled, /ready must return 404."""
        response = await client_no_ready.get("/ready")
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_health_still_reachable_when_ready_disabled(
        self, client_no_ready: AsyncTestClient
    ) -> None:
        """Disabling /ready must not affect /health -- they are independent flags."""
        response = await client_no_ready.get("/health")
        assert response.status_code == HTTP_200_OK

    async def test_v1_facts_still_reachable_when_ready_disabled(
        self, client_no_ready: AsyncTestClient
    ) -> None:
        """Disabling /ready must not affect the main API endpoints."""
        response = await client_no_ready.post(
            "/v1/facts",
            json={"system_facts": {}, "package_facts": {}},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert response.status_code != HTTP_404_NOT_FOUND
