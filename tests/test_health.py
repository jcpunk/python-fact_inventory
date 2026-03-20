"""
Tests for the unversioned /fact_inventory/health endpoint.
"""

from unittest.mock import AsyncMock, patch

from litestar.status_codes import HTTP_200_OK, HTTP_405_METHOD_NOT_ALLOWED
from litestar.testing import AsyncTestClient


class TestHealthCheck:
    """Tests for GET /fact_inventory/health."""

    async def test_health_returns_ok(self, client: AsyncTestClient) -> None:
        """The health endpoint must respond with HTTP 200."""
        response = await client.get("/fact_inventory/health")
        assert response.status_code == HTTP_200_OK

    async def test_health_body_status(self, client: AsyncTestClient) -> None:
        """Response body must contain status 'ok'."""
        response = await client.get("/fact_inventory/health")
        assert response.json()["status"] == "ok"

    async def test_health_body_service(self, client: AsyncTestClient) -> None:
        """Response body must identify the service as 'fact_inventory'."""
        response = await client.get("/fact_inventory/health")
        assert response.json()["service"] == "fact_inventory"

    async def test_health_content_type(self, client: AsyncTestClient) -> None:
        """Response must be JSON."""
        response = await client.get("/fact_inventory/health")
        assert "application/json" in response.headers["content-type"]

    async def test_health_no_extra_fields(self, client: AsyncTestClient) -> None:
        """Response body must contain exactly the documented fields."""
        response = await client.get("/fact_inventory/health")
        assert set(response.json().keys()) == {"status", "service"}

    async def test_health_post_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; POST must be rejected."""
        response = await client.post("/fact_inventory/health", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_health_put_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; PUT must be rejected."""
        response = await client.put("/fact_inventory/health", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_health_delete_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; DELETE must be rejected."""
        response = await client.delete("/fact_inventory/health")
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_health_patch_not_allowed(self, client: AsyncTestClient) -> None:
        """Only GET is allowed; PATCH must be rejected."""
        response = await client.patch("/fact_inventory/health")
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_health_is_reachable_without_auth(
        self, client: AsyncTestClient
    ) -> None:
        """Health check must be reachable without any credentials."""
        response = await client.get("/fact_inventory/health")
        # If any auth guard were in place this would be 401/403
        assert response.status_code == HTTP_200_OK

    async def test_health_repeated_calls_are_consistent(
        self, client: AsyncTestClient
    ) -> None:
        """Multiple successive calls must all return the same response."""
        for _ in range(3):
            response = await client.get("/fact_inventory/health")
            assert response.status_code == HTTP_200_OK
            assert response.json() == {"status": "ok", "service": "fact_inventory"}

    async def test_health_independent_of_db_failure(
        self, client: AsyncTestClient
    ) -> None:
        """Liveness probe must return 200 even when a DB dependency fails."""
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
            side_effect=Exception("simulated failure"),
        ):
            response = await client.get("/fact_inventory/health")
        assert response.status_code == HTTP_200_OK

    async def test_health_not_rate_limited(self, client: AsyncTestClient) -> None:
        """Health probe must never be throttled by the rate limiter."""
        for _ in range(5):
            response = await client.get("/fact_inventory/health")
            assert response.status_code == HTTP_200_OK
