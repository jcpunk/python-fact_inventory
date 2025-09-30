"""
Tests for the unversioned /fact_inventory/ready endpoint.
"""

from unittest.mock import AsyncMock, patch

from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from litestar.testing import AsyncTestClient


class TestReadinessCheck:
    """Tests for GET /fact_inventory/ready."""

    async def test_ready_returns_ok(self, client: AsyncTestClient) -> None:
        """The readiness endpoint must respond with HTTP 200 when the DB is up."""
        response = await client.get("/fact_inventory/ready")
        assert response.status_code == HTTP_200_OK

    async def test_ready_body_status(self, client: AsyncTestClient) -> None:
        """Response body must contain status 'ok'."""
        response = await client.get("/fact_inventory/ready")
        assert response.json()["status"] == "ok"

    async def test_ready_body_service(self, client: AsyncTestClient) -> None:
        """Response body must identify the service as 'fact_inventory'."""
        response = await client.get("/fact_inventory/ready")
        assert response.json()["service"] == "fact_inventory"

    async def test_ready_content_type(self, client: AsyncTestClient) -> None:
        """Response must be JSON."""
        response = await client.get("/fact_inventory/ready")
        assert "application/json" in response.headers["content-type"]

    async def test_ready_no_extra_fields(self, client: AsyncTestClient) -> None:
        """Response body must contain exactly the documented fields."""
        response = await client.get("/fact_inventory/ready")
        assert set(response.json().keys()) == {"status", "service"}

    async def test_ready_post_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; POST must be rejected."""
        response = await client.post("/fact_inventory/ready", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_ready_put_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; PUT must be rejected."""
        response = await client.put("/fact_inventory/ready", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_ready_delete_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; DELETE must be rejected."""
        response = await client.delete("/fact_inventory/ready")
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
            response = await client.get("/fact_inventory/ready")
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE

    async def test_ready_db_failure_body(self, client: AsyncTestClient) -> None:
        """When the database is unreachable, the response body must contain a detail."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            response = await client.get("/fact_inventory/ready")
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
            response = await client.get("/fact_inventory/ready")
        detail = response.json()["detail"].lower()
        assert "database" not in detail
        assert "sql" not in detail
        assert "select" not in detail

    async def test_ready_patch_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; PATCH must be rejected."""
        response = await client.patch("/fact_inventory/ready")
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
            response = await client.get("/fact_inventory/ready")
        assert "application/json" in response.headers["content-type"]

    async def test_ready_503_has_only_detail_key(self, client: AsyncTestClient) -> None:
        """503 body must contain standard Litestar error keys only."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("db unavailable"),
        ):
            response = await client.get("/fact_inventory/ready")
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
            response = await client.get("/fact_inventory/ready")
        assert some_message not in response.text

    async def test_ready_repeated_calls_consistent(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Multiple successive calls must all return the same response."""
        for _ in range(3):
            response = await client.get("/fact_inventory/ready")
            assert response.status_code == HTTP_200_OK
            assert response.json() == {"status": "ok", "service": "fact_inventory"}

    async def test_ready_is_distinct_from_health(
        self,
        client: AsyncTestClient,
    ) -> None:
        """The readiness probe lives at a different path than the liveness probe."""
        health = await client.get("/fact_inventory/health")
        ready = await client.get("/fact_inventory/ready")
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
            ready = await client.get("/fact_inventory/ready")
            health = await client.get("/fact_inventory/health")
        assert ready.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert health.status_code == HTTP_200_OK
