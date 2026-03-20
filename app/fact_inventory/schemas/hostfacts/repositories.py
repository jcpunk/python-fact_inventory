from datetime import datetime

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import delete, func, select

from .models import HostFacts


class HostFactsRepository(SQLAlchemyAsyncRepository[HostFacts]):
    """
    This is the database logic it should have some knowledge of how the
    database is setup, how to query it, and other behaviors that are not
    abstracted away from the db interface.

    It should only have database specific workflows.
    """

    model_type = HostFacts

    async def exists_recent_update_for_client(
        self, client_address: str, since: datetime
    ) -> bool:
        stmt = (
            select(self.model_type.updated_at)
            .where(
                self.model_type.client_address == client_address,
                self.model_type.updated_at >= since,
            )
            .limit(1)
        )
        result: datetime | None = await self.session.scalar(stmt)
        return result is not None

    async def exists_recent_entry_for_client(
        self, client_address: str, since: datetime
    ) -> bool:
        stmt = (
            select(self.model_type.created_at)
            .where(
                self.model_type.client_address == client_address,
                self.model_type.created_at >= since,
            )
            .limit(1)
        )
        result: datetime | None = await self.session.scalar(stmt)
        return result is not None

    async def delete_hosts_not_updated_since(self, cutoff: datetime) -> int:
        """Delete all host records whose ``updated_at`` is older than *cutoff*.

        Returns the number of rows deleted.
        """
        count_stmt = (
            select(func.count())
            .select_from(self.model_type)
            .where(self.model_type.updated_at < cutoff)
        )
        count: int = await self.session.scalar(count_stmt) or 0

        if count:
            delete_stmt = delete(self.model_type).where(
                self.model_type.updated_at < cutoff
            )
            await self.session.execute(delete_stmt)
            await self.session.commit()

        return count
