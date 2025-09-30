"""Database access layer for the ``fact_inventory`` table."""

from datetime import datetime
from typing import Any, cast

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import CursorResult, delete

from .models import FactInventory


class FactInventoryRepository(SQLAlchemyAsyncRepository[FactInventory]):
    """Database access layer for the ``fact_inventory`` table.

    Methods here contain database-specific query logic (raw SQL
    constructs, dialect hints, etc.).  Application rules belong in
    :class:`~app.v1.services.FactInventoryService`.
    """

    model_type = FactInventory

    async def delete_facts_not_updated_since(self, cutoff: datetime) -> int:
        """Delete all fact records whose ``updated_at`` is older than *cutoff*.

        Returns the number of rows deleted.  Uses a single DELETE
        statement and reads the row count from the database cursor.

        ``session.execute()`` on a DML statement returns a
        ``CursorResult`` at runtime, but the async stub types it as
        ``Result[Any]``.  We use ``cast`` to bridge the gap without
        suppressing type checking.
        """
        stmt = delete(self.model_type).where(self.model_type.updated_at < cutoff)
        result = cast("CursorResult[Any]", await self.session.execute(stmt))
        count: int = result.rowcount
        if count:
            await self.session.commit()
        return count
