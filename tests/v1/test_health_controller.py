"""
Tests for the HealthController endpoint.
"""

from litestar.status_codes import HTTP_200_OK
from litestar.testing import AsyncTestClient


class TestHealthController:
    """Tests for the GET /v1/healthz endpoint."""

    async def test_healthz_returns_ok(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test health check returns 200 when the database is reachable."""
        response = await client.get("/v1/healthz")

        assert response.status_code == HTTP_200_OK
        assert response.json()["detail"] == "ok"
