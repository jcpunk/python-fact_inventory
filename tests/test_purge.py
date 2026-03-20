"""
Tests for the host retention / purge logic in the service and repository layers.
"""

from advanced_alchemy.extensions.litestar import SQLAlchemyPlugin
from app.fact_inventory.schemas.hostfacts import HostFacts
from app.fact_inventory.v1.services import HostFactsService
from litestar.status_codes import HTTP_201_CREATED
from litestar.testing import AsyncTestClient
from sqlalchemy import select


def _get_alchemy_config(client: AsyncTestClient):  # type: ignore[no-untyped-def]
    """Extract the SQLAlchemyAsyncConfig from the Litestar app."""
    plugin: SQLAlchemyPlugin = next(
        p for p in client.app.plugins if isinstance(p, SQLAlchemyPlugin)
    )
    # _config is a list of config objects; we use the first (and only) one
    return plugin._config[0]


class TestPurgeExpiredHosts:
    """Tests for HostFactsService.purge_expired_hosts and repository method."""

    async def test_purge_removes_old_hosts(self, client: AsyncTestClient) -> None:
        """Hosts older than the retention window must be deleted."""
        response = await client.post(
            "/fact_inventory/v1/facts",
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
            "/fact_inventory/v1/facts",
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
