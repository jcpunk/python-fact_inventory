"""Tests for GET /ready readiness endpoint."""

import asyncio
from unittest.mock import AsyncMock, patch

from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from litestar.testing import AsyncTestClient


async def test_returns_200_when_db_available(client: AsyncTestClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == HTTP_200_OK
    assert response.json() is None


async def test_post_not_allowed(client: AsyncTestClient) -> None:
    assert (
        await client.post("/ready", json={})
    ).status_code == HTTP_405_METHOD_NOT_ALLOWED


async def test_returns_503_on_db_failure(client: AsyncTestClient) -> None:
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        new_callable=AsyncMock,
        side_effect=Exception("db down"),
    ):
        response = await client.get("/ready")
    # Drain the event loop so aiosqlite's worker thread can post its
    # cleanup callback before pytest tears down the loop.
    await asyncio.sleep(0)
    assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
    assert "detail" in response.json()


async def test_returns_503_on_timeout(client: AsyncTestClient) -> None:
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        new_callable=AsyncMock,
        side_effect=TimeoutError("timeout"),
    ):
        response = await client.get("/ready")
    await asyncio.sleep(0)
    assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE


async def test_health_still_ok_when_ready_fails(client: AsyncTestClient) -> None:
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        new_callable=AsyncMock,
        side_effect=Exception("db down"),
    ):
        health = await client.get("/health")
        ready = await client.get("/ready")
    await asyncio.sleep(0)
    assert health.status_code == HTTP_200_OK
    assert ready.status_code == HTTP_503_SERVICE_UNAVAILABLE


async def test_returns_404_when_disabled(client_no_ready: AsyncTestClient) -> None:
    assert (await client_no_ready.get("/ready")).status_code == HTTP_404_NOT_FOUND


async def test_health_unaffected_when_ready_disabled(
    client_no_ready: AsyncTestClient,
) -> None:
    assert (await client_no_ready.get("/health")).status_code == HTTP_200_OK


async def test_works_when_health_disabled(client_no_health: AsyncTestClient) -> None:
    assert (await client_no_health.get("/ready")).status_code == HTTP_200_OK
