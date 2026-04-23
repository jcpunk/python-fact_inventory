"""Business-logic layer for the fact_inventory v1 API."""

import datetime
import logging
from typing import Any

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ..schemas import FactInventory, FactInventoryRepository

logger = logging.getLogger(__name__)


class FactInventoryService(SQLAlchemyAsyncRepositoryService[FactInventory]):
    """Business-logic layer for fact inventory records.

    Methods here express *application* rules (retention, upsert
    strategy) while delegating database-specific work to
    :class:`FactInventoryRepository`.
    """

    model_type = FactInventory
    repository_type = FactInventoryRepository
    repository: FactInventoryRepository

    async def upsert_facts(self, data: dict[str, Any]) -> None:
        """Create or update a fact inventory record.

        Matching is based on ``client_address`` -- if a record exists for
        the same IP it is updated in place and ``updated_at`` is
        refreshed; otherwise a new record is created.

        Parameters
        ----------
        data:
            Dictionary containing ``client_address``, ``system_facts``,
            ``package_facts``, and ``local_facts``.
        """
        await self.upsert(
            data=data,
            match_fields=["client_address"],
            auto_commit=True,
        )

    async def purge_expired_facts(self, retention_days: int) -> int:
        """Delete fact records not updated within *retention_days*.

        Parameters
        ----------
        retention_days:
            Records with ``updated_at`` older than this many days in the
            past are deleted.

        Returns
        -------
        int
            Number of records deleted.  All timestamp comparisons use UTC.
        """
        cutoff = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
            days=retention_days
        )
        cutoff_date = cutoff.date().isoformat()
        count = await self.repository.delete_facts_not_updated_since(cutoff)
        if count:
            logger.info("Purged %d fact(s) not updated since %s", count, cutoff_date)
        else:
            logger.debug("No expired facts to purge (cutoff=%s)", cutoff_date)
        return count
