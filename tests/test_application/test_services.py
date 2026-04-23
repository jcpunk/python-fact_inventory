"""Tests for FactInventoryService business logic."""

from datetime import UTC, datetime, timedelta

import pytest
from fact_inventory.application.exceptions import FactValidationError
from fact_inventory.application.services import FactInventoryService
from fact_inventory.config.settings import settings
from fact_inventory.infrastructure.db.models import FactInventory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestUpsertRecord:
    async def test_creates_new_record(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.upsert_client_record(
            {
                "client_address": "192.0.2.100",
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.100")
        )
        assert result.scalar_one().system_facts == {"os": "RHEL"}

    async def test_updates_existing_record(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        ip = "192.0.2.101"
        await service.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "1"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        original_id = result.scalar_one().id

        await service.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "2"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        record = result.scalar_one()
        assert record.id == original_id
        assert record.system_facts["v"] == "2"

    async def test_preserves_id(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        ip = "192.0.2.102"
        await service.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        record1 = result.scalar_one()
        id1 = record1.id

        await service.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        record2 = result.scalar_one()
        assert record2.id == id1

    async def test_refreshes_updated_at(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        ip = "192.0.2.103"
        await service.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "1"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        record1 = result.scalar_one()
        original_id = record1.id

        await service.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "2"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        record2 = result.scalar_one()
        assert record2.id == original_id
        assert record2.system_facts["v"] == "2"

    async def test_maintains_one_record_per_ip(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        ip = "192.0.2.104"
        data = {
            "client_address": ip,
            "system_facts": {"os": "RHEL"},
            "package_facts": {},
            "local_facts": {},
        }
        await service.upsert_client_record(data)
        await service.upsert_client_record(data)
        await service.upsert_client_record(data)
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        assert len(result.scalars().all()) == 1

    async def test_rejects_all_empty_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        with pytest.raises(FactValidationError, match="fact"):
            await service.upsert_client_record(
                {
                    "client_address": "192.0.2.10",
                    "system_facts": {},
                    "package_facts": {},
                    "local_facts": {},
                }
            )

    async def test_rejects_oversized_system_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match=r"system_facts.*exceeds"):
            await service.upsert_client_record(
                {
                    "client_address": "192.0.2.1",
                    "system_facts": {"data": oversized},
                    "package_facts": {},
                    "local_facts": {},
                }
            )

    async def test_rejects_oversized_package_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match=r"package_facts.*exceeds"):
            await service.upsert_client_record(
                {
                    "client_address": "192.0.2.2",
                    "system_facts": {},
                    "package_facts": {"data": oversized},
                    "local_facts": {},
                }
            )

    async def test_rejects_oversized_local_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match=r"local_facts.*exceeds"):
            await service.upsert_client_record(
                {
                    "client_address": "192.0.2.3",
                    "system_facts": {},
                    "package_facts": {},
                    "local_facts": {"data": oversized},
                }
            )

    async def test_accepts_at_limit(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        at_limit = "x" * (settings.max_json_field_mb * 1024 * 1024 - 12)
        await service.upsert_client_record(
            {
                "client_address": "192.0.2.4",
                "system_facts": {"data": at_limit},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.4")
        )
        assert result.scalar_one() is not None

    async def test_accepts_system_facts_only(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.upsert_client_record(
            {
                "client_address": "192.0.2.12",
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.12")
        )
        assert result.scalar_one() is not None

    async def test_accepts_package_facts_only(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.upsert_client_record(
            {
                "client_address": "192.0.2.13",
                "system_facts": {},
                "package_facts": {"glibc": "2.36"},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.13")
        )
        assert result.scalar_one() is not None

    async def test_accepts_local_facts_only(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.upsert_client_record(
            {
                "client_address": "192.0.2.14",
                "system_facts": {},
                "package_facts": {},
                "local_facts": {"env": "prod"},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.14")
        )
        assert result.scalar_one() is not None


class TestInsertRecord:
    async def test_creates_new_row(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.insert_record(
            {
                "client_address": "192.0.2.200",
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.200")
        )
        assert result.scalar_one().system_facts == {"os": "RHEL"}

    async def test_allows_multiple_rows_per_ip(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        ip = "192.0.2.201"
        data = {
            "client_address": ip,
            "system_facts": {"os": "RHEL"},
            "package_facts": {},
            "local_facts": {},
        }
        await service.insert_record(data)
        await service.insert_record(data)
        await service.insert_record(data)
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        assert len(result.scalars().all()) == 3

    async def test_creates_unique_ids(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        ip = "192.0.2.202"
        await service.insert_record(
            {
                "client_address": ip,
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        await service.insert_record(
            {
                "client_address": ip,
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        records = result.scalars().all()
        id1 = records[0].id
        id2 = records[1].id
        assert id1 != id2

    async def test_rejects_all_empty_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        with pytest.raises(FactValidationError):
            await service.insert_record(
                {
                    "client_address": "192.0.2.11",
                    "system_facts": {},
                    "package_facts": {},
                    "local_facts": {},
                }
            )

    async def test_rejects_oversized_system_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match=r"system_facts.*exceeds"):
            await service.insert_record(
                {
                    "client_address": "192.0.2.5",
                    "system_facts": {"data": oversized},
                    "package_facts": {},
                    "local_facts": {},
                }
            )

    async def test_rejects_oversized_package_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match=r"package_facts.*exceeds"):
            await service.insert_record(
                {
                    "client_address": "192.0.2.6",
                    "system_facts": {},
                    "package_facts": {"data": oversized},
                    "local_facts": {},
                }
            )

    async def test_rejects_oversized_local_facts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        oversized = "x" * (settings.max_json_field_mb * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match=r"local_facts.*exceeds"):
            await service.insert_record(
                {
                    "client_address": "192.0.2.7",
                    "system_facts": {},
                    "package_facts": {},
                    "local_facts": {"data": oversized},
                }
            )

    async def test_accepts_at_limit(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        at_limit = "x" * (settings.max_json_field_mb * 1024 * 1024 - 12)
        await service.insert_record(
            {
                "client_address": "192.0.2.8",
                "system_facts": {"data": at_limit},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.8")
        )
        assert result.scalar_one() is not None

    async def test_accepts_system_facts_only(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.insert_record(
            {
                "client_address": "192.0.2.12",
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.12")
        )
        assert result.scalar_one() is not None

    async def test_accepts_package_facts_only(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.insert_record(
            {
                "client_address": "192.0.2.13",
                "system_facts": {},
                "package_facts": {"glibc": "2.36"},
                "local_facts": {},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.13")
        )
        assert result.scalar_one() is not None

    async def test_accepts_local_facts_only(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        await service.insert_record(
            {
                "client_address": "192.0.2.14",
                "system_facts": {},
                "package_facts": {},
                "local_facts": {"env": "prod"},
            }
        )
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == "192.0.2.14")
        )
        assert result.scalar_one() is not None


class TestPurgeFactsOlderThan:
    async def test_removes_old_records(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        db_session_from_app.add_all(
            [
                FactInventory(
                    client_address="192.0.2.50",
                    system_facts={"age": "old"},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=30),
                    updated_at=now - timedelta(days=30),
                ),
                FactInventory(
                    client_address="192.0.2.51",
                    system_facts={"age": "new"},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(days=2),
                ),
            ]
        )
        await db_session_from_app.commit()
        assert await service.purge_facts_older_than(retention_days=10) == 1

    async def test_keeps_recent_records(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        db_session_from_app.add(
            FactInventory(
                client_address="192.0.2.52",
                system_facts={},
                package_facts={},
                local_facts={},
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            )
        )
        await db_session_from_app.commit()
        assert await service.purge_facts_older_than(retention_days=10) == 0

    async def test_returns_deleted_count(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        for i in range(3):
            db_session_from_app.add(
                FactInventory(
                    client_address=f"192.0.2.{100 + i}",
                    system_facts={},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=30),
                    updated_at=now - timedelta(days=30),
                )
            )
        await db_session_from_app.commit()
        assert await service.purge_facts_older_than(retention_days=10) == 3


class TestPurgeFactsOverLimit:
    async def test_keeps_newest_per_ip(self, db_session_from_app: AsyncSession) -> None:
        service = FactInventoryService(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        ip = "192.0.2.60"
        for i in range(5):
            db_session_from_app.add(
                FactInventory(
                    client_address=ip,
                    system_facts={"i": i},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=5 - i),
                    updated_at=now - timedelta(days=5 - i),
                )
            )
        await db_session_from_app.commit()
        assert await service.purge_fact_history_more_than(max_entries=3) == 2
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        assert len(result.scalars().all()) == 3

    async def test_keeps_all_when_under_limit(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        db_session_from_app.add(
            FactInventory(
                client_address="192.0.2.62",
                system_facts={},
                package_facts={},
                local_facts={},
                created_at=now,
                updated_at=now,
            )
        )
        await db_session_from_app.commit()
        assert await service.purge_fact_history_more_than(max_entries=5) == 0

    async def test_returns_deleted_count(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        for i in range(7):
            db_session_from_app.add(
                FactInventory(
                    client_address="192.0.2.61",
                    system_facts={"i": i},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=7 - i),
                    updated_at=now - timedelta(days=7 - i),
                )
            )
        await db_session_from_app.commit()
        assert await service.purge_fact_history_more_than(max_entries=5) == 2

    async def test_rejects_zero_max_entries(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        with pytest.raises(ValueError, match="between 1 and 1000"):
            await service.purge_fact_history_more_than(max_entries=0)

    async def test_rejects_negative_max_entries(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        with pytest.raises(ValueError, match="between 1 and 1000"):
            await service.purge_fact_history_more_than(max_entries=-5)

    async def test_rejects_excessive_max_entries(
        self, db_session_from_app: AsyncSession
    ) -> None:
        service = FactInventoryService(session=db_session_from_app)
        with pytest.raises(ValueError, match="between 1 and 1000"):
            await service.purge_fact_history_more_than(max_entries=1001)
