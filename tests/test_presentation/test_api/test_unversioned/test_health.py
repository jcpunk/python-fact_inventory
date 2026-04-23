"""Tests for GET /health liveness endpoint."""

import asyncio
from unittest.mock import AsyncMock, patch

from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
)
from litestar.testing import AsyncTestClient


async def test_returns_200_with_ok_status(client: AsyncTestClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_200_OK
    assert response.json() is None


async def test_post_not_allowed(client: AsyncTestClient) -> None:
    assert (
        await client.post("/health", json={})
    ).status_code == HTTP_405_METHOD_NOT_ALLOWED


async def test_independent_of_db_failure(client: AsyncTestClient) -> None:
    # /health has no DB call, but the patch is here to confirm that even if
    # the session were used, health remains independent. The drain sleep is
    # included defensively to avoid aiosqlite thread teardown warnings.
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        new_callable=AsyncMock,
        side_effect=Exception("db down"),
    ):
        response = await client.get("/health")
    await asyncio.sleep(0)
    assert response.status_code == HTTP_200_OK


async def test_returns_404_when_disabled(client_no_health: AsyncTestClient) -> None:
    assert (await client_no_health.get("/health")).status_code == HTTP_404_NOT_FOUND


async def test_ready_unaffected_when_health_disabled(
    client_no_health: AsyncTestClient,
) -> None:
    assert (await client_no_health.get("/ready")).status_code == HTTP_200_OK


async def test_works_when_ready_disabled(client_only_health: AsyncTestClient) -> None:
    assert (await client_only_health.get("/health")).status_code == HTTP_200_OK
