from datetime import datetime

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import delete, func, select

from .models import HostFacts


class HostFactsRepository(SQLAlchemyAsyncRepository[HostFacts]):
    """Database access layer for the ``host_facts`` table.

    Methods here contain database-specific query logic (raw SQL
    constructs, dialect hints, etc.).  Application rules belong in
    :class:`~app.fact_inventory.v1.services.HostFactsService`.
    """

    model_type = HostFacts

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
