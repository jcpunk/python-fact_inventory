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
        """Delete all fact records whose ``updated_at`` predates *cutoff*.

        Parameters
        ----------
        cutoff:
            Deletion threshold; records with ``updated_at < cutoff`` are
            removed.

        Returns
        -------
        int
            Number of rows deleted.  Includes an automatic ``COMMIT`` if
            rows were deleted.
        """
        stmt = delete(self.model_type).where(self.model_type.updated_at < cutoff)
        result = cast("CursorResult[Any]", await self.session.execute(stmt))
        count: int = result.rowcount
        if count:
            await self.session.commit()
        return count
