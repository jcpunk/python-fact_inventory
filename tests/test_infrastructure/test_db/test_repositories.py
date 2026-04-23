"""Tests for FactInventoryRepository database operations."""

from datetime import UTC, datetime, timedelta

from fact_inventory.domain.retention import HistoryRetentionPolicy, TimeRetentionPolicy
from fact_inventory.infrastructure.db.models import FactInventory
from fact_inventory.infrastructure.db.repositories import FactInventoryRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestInsertRecord:
    async def test_creates_record(self, db_session_from_app: AsyncSession) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        result = await repo.insert_record(
            {
                "client_address": "192.0.2.100",
                "system_facts": {"os": "RHEL"},
                "package_facts": {"curl": "7.68"},
                "local_facts": {"k": "v"},
            }
        )
        assert result.client_address == "192.0.2.100"
        assert result.system_facts == {"os": "RHEL"}

    async def test_allows_multiple_rows_same_ip(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        data = {
            "client_address": "192.0.2.101",
            "system_facts": {},
            "package_facts": {},
            "local_facts": {},
        }
        r1 = await repo.insert_record(data)
        r2 = await repo.insert_record(data)
        r3 = await repo.insert_record(data)
        assert r1.id != r2.id != r3.id

    async def test_returns_fact_inventory_instance(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        result = await repo.insert_record(
            {
                "client_address": "192.0.2.102",
                "system_facts": {},
                "package_facts": {},
                "local_facts": {},
            }
        )
        assert isinstance(result, FactInventory)
        assert result.id is not None


class TestUpsertRecord:
    async def test_creates_when_not_exists(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        result = await repo.upsert_client_record(
            {
                "client_address": "192.0.2.200",
                "system_facts": {"os": "RHEL"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        assert result.client_address == "192.0.2.200"

    async def test_updates_when_exists(self, db_session_from_app: AsyncSession) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        ip = "192.0.2.201"
        r1 = await repo.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "1"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        r2 = await repo.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "2"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        assert r2.id == r1.id
        assert r2.system_facts["v"] == "2"

    async def test_preserves_id_across_upserts(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        ip = "192.0.2.202"
        data = {
            "client_address": ip,
            "system_facts": {},
            "package_facts": {},
            "local_facts": {},
        }
        id1 = (await repo.upsert_client_record(data)).id
        id2 = (await repo.upsert_client_record(data)).id
        assert id1 == id2

    async def test_refreshes_updated_at_on_update(
        self, db_session_from_app: AsyncSession
    ) -> None:
        import asyncio as _asyncio

        repo = FactInventoryRepository(session=db_session_from_app)
        ip = "192.0.2.203"
        r1 = await repo.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "1"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        original_updated_at = r1.updated_at
        await _asyncio.sleep(0.01)
        r2 = await repo.upsert_client_record(
            {
                "client_address": ip,
                "system_facts": {"v": "2"},
                "package_facts": {},
                "local_facts": {},
            }
        )
        assert r2.id == r1.id
        assert r2.updated_at >= original_updated_at


class TestDeleteFactsOlderThan:
    async def test_removes_expired_records(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        db_session_from_app.add_all(
            [
                FactInventory(
                    client_address="192.0.2.1",
                    system_facts={},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=10),
                    updated_at=now - timedelta(days=10),
                ),
                FactInventory(
                    client_address="192.0.2.2",
                    system_facts={},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(days=2),
                ),
            ]
        )
        await db_session_from_app.commit()
        assert await repo.delete_facts_older_than(TimeRetentionPolicy(5)) == 1

    async def test_keeps_recent_records(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        db_session_from_app.add(
            FactInventory(
                client_address="192.0.2.3",
                system_facts={},
                package_facts={},
                local_facts={},
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            )
        )
        await db_session_from_app.commit()
        assert await repo.delete_facts_older_than(TimeRetentionPolicy(10)) == 0

    async def test_empty_table_returns_zero(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        assert await repo.delete_facts_older_than(TimeRetentionPolicy(5)) == 0


class TestFactInventoryModel:
    async def test_repr(self, db_session_from_app: AsyncSession) -> None:
        now = datetime.now(tz=UTC)
        record = FactInventory(
            client_address="192.0.2.100",
            system_facts={},
            package_facts={},
            local_facts={},
            created_at=now,
            updated_at=now,
        )
        repr_str = repr(record)
        assert "FactInventory" in repr_str
        assert "192.0.2.100" in repr_str

    async def test_all_expired_deletes_all(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        for i in range(3):
            db_session_from_app.add(
                FactInventory(
                    client_address=f"192.0.2.{i}",
                    system_facts={},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(days=10),
                    updated_at=now - timedelta(days=10),
                )
            )
        await db_session_from_app.commit()
        assert await repo.delete_facts_older_than(TimeRetentionPolicy(5)) == 3


class TestDeleteFactsOverLimit:
    async def test_keeps_newest_per_ip(self, db_session_from_app: AsyncSession) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        ip = "192.0.2.4"
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
        policy = HistoryRetentionPolicy(max_entries=3)
        assert await repo.delete_old_client_facts_over_limit(policy) == 2
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        assert len(result.scalars().all()) == 3

    async def test_limit_applies_per_ip_independently(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        for ip in ("192.0.2.5", "192.0.2.6"):
            for i in range(5):
                db_session_from_app.add(
                    FactInventory(
                        client_address=ip,
                        system_facts={},
                        package_facts={},
                        local_facts={},
                        created_at=now - timedelta(days=5 - i),
                        updated_at=now - timedelta(days=5 - i),
                    )
                )
        await db_session_from_app.commit()
        policy = HistoryRetentionPolicy(max_entries=3)
        assert await repo.delete_old_client_facts_over_limit(policy) == 4

    async def test_empty_table_returns_zero(
        self, db_session_from_app: AsyncSession
    ) -> None:
        repo = FactInventoryRepository(session=db_session_from_app)
        policy = HistoryRetentionPolicy(max_entries=5)
        assert await repo.delete_old_client_facts_over_limit(policy) == 0

    async def test_removes_excess_per_single_client(
        self, db_session_from_app: AsyncSession
    ) -> None:
        """Boundary: exactly one client, excess beyond limit are deleted."""
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        ip = "192.0.2.11"
        for i in range(5):
            db_session_from_app.add(
                FactInventory(
                    client_address=ip,
                    system_facts={},
                    package_facts={},
                    local_facts={},
                    created_at=now - timedelta(minutes=i * 10),
                    updated_at=now - timedelta(minutes=i * 10),
                )
            )
        await db_session_from_app.commit()
        policy = HistoryRetentionPolicy(max_entries=3)
        assert await repo.delete_old_client_facts_over_limit(policy) == 2
        result = await db_session_from_app.execute(
            select(FactInventory).where(FactInventory.client_address == ip)
        )
        assert len(result.scalars().all()) == 3

    async def test_window_function_partition_independence(
        self, db_session_from_app: AsyncSession
    ) -> None:
        """PARTITION BY client_address ensures each IP is capped independently."""
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        for ip in ("192.0.2.200", "192.0.2.201"):
            for i in range(5):
                db_session_from_app.add(
                    FactInventory(
                        client_address=ip,
                        system_facts={"client": ip, "i": i},
                        package_facts={},
                        local_facts={},
                        created_at=now - timedelta(days=5 - i),
                        updated_at=now - timedelta(days=5 - i),
                    )
                )
        await db_session_from_app.commit()
        policy = HistoryRetentionPolicy(max_entries=3)
        assert await repo.delete_old_client_facts_over_limit(policy) == 4
        for ip in ("192.0.2.200", "192.0.2.201"):
            result = await db_session_from_app.execute(
                select(FactInventory).where(FactInventory.client_address == ip)
            )
            assert len(result.scalars().all()) == 3

    async def test_window_function_keeps_newest(
        self, db_session_from_app: AsyncSession
    ) -> None:
        """Window function row_number() OVER (PARTITION BY ... ORDER BY created_at DESC) keeps newest N."""
        repo = FactInventoryRepository(session=db_session_from_app)
        now = datetime.now(tz=UTC)
        ip = "192.0.2.100"
        created_times = [now - timedelta(days=4 - i) for i in range(5)]
        for idx, ts in enumerate(created_times):
            db_session_from_app.add(
                FactInventory(
                    client_address=ip,
                    system_facts={"idx": idx},
                    package_facts={},
                    local_facts={},
                    created_at=ts,
                    updated_at=ts,
                )
            )
        await db_session_from_app.commit()

        policy = HistoryRetentionPolicy(max_entries=3)
        assert await repo.delete_old_client_facts_over_limit(policy) == 2

        result = await db_session_from_app.execute(
            select(FactInventory)
            .where(FactInventory.client_address == ip)
            .order_by(FactInventory.created_at.desc())
        )
        remaining = result.scalars().all()
        assert len(remaining) == 3
        remaining_times = sorted([r.created_at for r in remaining], reverse=True)
        expected_times = sorted(created_times[-3:], reverse=True)
        assert remaining_times == expected_times
