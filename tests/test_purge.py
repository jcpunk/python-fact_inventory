"""
Tests for the host retention / purge logic in the service and repository layers.
"""

from typing import Any

from advanced_alchemy.extensions.litestar import (
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from app.schemas import HostFacts
from app.v1.services import HostFactsService
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


class TestPurgeExpiredHosts:
    """Tests for HostFactsService.purge_expired_hosts and repository method."""

    async def test_purge_removes_old_hosts(self, client: AsyncTestClient) -> None:
        """Hosts older than the retention window must be deleted."""
        response = await client.post(
            "/v1/facts",
            json={"system_facts": {"os": "test"}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED

        config = _get_alchemy_config(client)
        async with config.get_session() as session:
            result = await session.execute(select(HostFacts))
            assert len(result.scalars().all()) >= 1

            service = HostFactsService(session)
            count = await service.purge_expired_hosts(retention_days=0)
            assert count >= 1

            result2 = await session.execute(select(HostFacts))
            assert len(result2.scalars().all()) == 0

    async def test_purge_keeps_recent_hosts(self, client: AsyncTestClient) -> None:
        """Hosts updated within the retention window must be kept."""
        response = await client.post(
            "/v1/facts",
            json={"system_facts": {"os": "keep-me"}, "package_facts": {}},
        )
        assert response.status_code == HTTP_201_CREATED

        config = _get_alchemy_config(client)
        async with config.get_session() as session:
            service = HostFactsService(session)
            count = await service.purge_expired_hosts(retention_days=365)
            assert count == 0

            result = await session.execute(select(HostFacts))
            assert len(result.scalars().all()) >= 1

    async def test_purge_returns_zero_on_empty_table(
        self, client: AsyncTestClient
    ) -> None:
        """Purge must return 0 when the table is empty."""
        config = _get_alchemy_config(client)
        async with config.get_session() as session:
            service = HostFactsService(session)
            count = await service.purge_expired_hosts(retention_days=0)
            assert count == 0
