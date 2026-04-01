from datetime import datetime

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import CursorResult, delete

from .models import HostFacts


class HostFactsRepository(SQLAlchemyAsyncRepository[HostFacts]):
    """Database access layer for the ``host_facts`` table.

    Methods here contain database-specific query logic (raw SQL
    constructs, dialect hints, etc.).  Application rules belong in
    :class:`~app.v1.services.HostFactsService`.
    """

    model_type = HostFacts

    async def delete_hosts_not_updated_since(self, cutoff: datetime) -> int:
        """Delete all host records whose ``updated_at`` is older than *cutoff*.

        Returns the number of rows deleted.  Uses a single DELETE
        statement and reads the row count from the database cursor.
        """
        stmt = delete(self.model_type).where(self.model_type.updated_at < cutoff)
        result: CursorResult[tuple[()]] = await self.session.execute(stmt)  # type: ignore[assignment]
        count: int = result.rowcount
        if count:
            await self.session.commit()
        return count
