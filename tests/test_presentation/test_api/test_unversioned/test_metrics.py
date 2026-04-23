"""Tests for GET /metrics Prometheus endpoint."""

from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
)
from litestar.testing import AsyncTestClient


async def test_returns_200_when_enabled(client: AsyncTestClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == HTTP_200_OK
    assert "fact_inventory" in response.text


async def test_post_not_allowed(client: AsyncTestClient) -> None:
    assert (
        await client.post("/metrics", json={})
    ).status_code == HTTP_405_METHOD_NOT_ALLOWED


async def test_returns_404_when_disabled(client_no_metrics: AsyncTestClient) -> None:
    assert (await client_no_metrics.get("/metrics")).status_code == HTTP_404_NOT_FOUND


async def test_v1_facts_unaffected_when_metrics_disabled(
    client_no_metrics: AsyncTestClient,
) -> None:
    response = await client_no_metrics.post(
        "/v1/facts", json={"system_facts": {}, "package_facts": {}, "local_facts": {}}
    )
    assert response.status_code != HTTP_404_NOT_FOUND


async def test_health_unaffected_when_metrics_disabled(
    client_no_metrics: AsyncTestClient,
) -> None:
    assert (await client_no_metrics.get("/health")).status_code == HTTP_200_OK


async def test_ready_unaffected_when_metrics_disabled(
    client_no_metrics: AsyncTestClient,
) -> None:
    assert (await client_no_metrics.get("/ready")).status_code == HTTP_200_OK
