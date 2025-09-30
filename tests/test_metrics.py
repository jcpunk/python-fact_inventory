"""
Tests for the Prometheus /metrics endpoint.
"""

from litestar.status_codes import HTTP_200_OK, HTTP_405_METHOD_NOT_ALLOWED
from litestar.testing import AsyncTestClient


class TestPrometheusMetrics:
    """Tests for the GET /metrics endpoint."""

    async def test_metrics_get_allowed(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that the Prometheus metrics endpoint is reachable."""
        response = await client.get("/metrics")

        assert response.status_code == HTTP_200_OK
        assert "fact_inventory" in response.text

    async def test_metrics_post_not_allowed(self, client: AsyncTestClient) -> None:
        """POST is not allowed on the metrics endpoint."""
        response = await client.post("/metrics", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_metrics_put_not_allowed(self, client: AsyncTestClient) -> None:
        """PUT is not allowed on the metrics endpoint."""
        response = await client.put("/metrics", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_metrics_delete_not_allowed(self, client: AsyncTestClient) -> None:
        """DELETE is not allowed on the metrics endpoint."""
        response = await client.delete("/metrics")
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED

    async def test_metrics_patch_not_allowed(self, client: AsyncTestClient) -> None:
        """PATCH is not allowed on the metrics endpoint."""
        response = await client.patch("/metrics", json={})
        assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED
