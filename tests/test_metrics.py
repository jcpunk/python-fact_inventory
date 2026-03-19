"""
Tests for the Prometheus /metrics endpoint.
"""

from litestar.status_codes import HTTP_200_OK
from litestar.testing import AsyncTestClient


class TestPrometheusMetrics:
    """Tests for the GET /metrics endpoint."""

    async def test_metrics_endpoint_returns_ok(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that the Prometheus metrics endpoint is reachable."""
        response = await client.get("/metrics")

        assert response.status_code == HTTP_200_OK
        assert "fact_inventory" in response.text
