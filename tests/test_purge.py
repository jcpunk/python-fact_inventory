"""
Tests for the fact inventory retention and purge logic.

Covers the service and repository layers.
"""

from typing import Any

from advanced_alchemy.extensions.litestar import (
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from app.schemas import FactInventory
from app.v1.services import FactInventoryService
from litestar.status_codes import HTTP_201_CREATED
from litestar.testing import AsyncTestClient
from sqlalchemy import select


def _get_alchemy_config(client: AsyncTestClient) -> SQLAlchemyAsyncConfig:
    """Extract the SQLAlchemyAsyncConfig from the Litestar app.

    Accesses ``SQLAlchemyPlugin._config`` which is an untyped private
    attribute (a list of config objects).  We take the first element and
    assert its type at runtime so that callers get proper type safety.
    """
    plugin: SQLAlchemyPlugin = next(
        p for p in client.app.plugins if isinstance(p, SQLAlchemyPlugin)
    )
    configs: list[Any] = plugin._config  # private, untyped attribute
    config = configs[0]
    assert isinstance(config, SQLAlchemyAsyncConfig)
    return config


class TestPurgeExpiredFacts:
    """Tests for FactInventoryService.purge_expired_facts and repository method."""

    async def test_purge_removes_old_facts(self, client: AsyncTestClient) -> None:
        """Facts older than the retention window must be deleted."""
        response = await client.post(
            "/v1/facts",
            json={"system_facts": {"os": "test"}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED

        config = _get_alchemy_config(client)
        async with config.get_session() as session:
            result = await session.execute(select(FactInventory))
            assert len(result.scalars().all()) >= 1

            service = FactInventoryService(session)
            count = await service.purge_expired_facts(retention_days=0)
            assert count >= 1

            result2 = await session.execute(select(FactInventory))
            assert len(result2.scalars().all()) == 0

    async def test_purge_keeps_recent_facts(self, client: AsyncTestClient) -> None:
        """Facts updated within the retention window must be kept."""
        response = await client.post(
            "/v1/facts",
            json={"system_facts": {"os": "keep-me"}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED

        config = _get_alchemy_config(client)
        async with config.get_session() as session:
            service = FactInventoryService(session)
            count = await service.purge_expired_facts(retention_days=400)
            assert count == 0

            result = await session.execute(select(FactInventory))
            assert len(result.scalars().all()) >= 1

    async def test_purge_returns_zero_on_empty_table(
        self, client: AsyncTestClient
    ) -> None:
        """Purge must return 0 when the table is empty."""
        config = _get_alchemy_config(client)
        async with config.get_session() as session:
            service = FactInventoryService(session)
            count = await service.purge_expired_facts(retention_days=0)
            assert count == 0
