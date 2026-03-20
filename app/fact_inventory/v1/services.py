import datetime
import logging
from typing import Any

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ..schemas.hostfacts import HostFacts, HostFactsRepository

logger = logging.getLogger(__name__)


class HostFactsService(SQLAlchemyAsyncRepositoryService[HostFacts]):
    """Business-logic layer for host fact records.

    Methods here express *application* rules (retention, upsert
    strategy) while delegating database-specific work to
    :class:`HostFactsRepository`.
    """

    model_type = HostFacts
    repository_type = HostFactsRepository
    repository: HostFactsRepository

    async def upsert_host_facts(self, data: dict[str, Any]) -> None:
        """Create or update a host fact record.

        Matching is based on ``client_address`` -- if a record already
        exists for the same IP the row is updated in place and its
        ``updated_at`` timestamp is refreshed.
        """
        await self.upsert(
            data=data,
            match_fields=["client_address"],
            auto_commit=True,
        )

    async def purge_expired_hosts(self, retention_days: int) -> int:
        """Delete host records not updated within *retention_days*.

        Returns the number of records purged.  Uses UTC for all
        timestamp comparisons.
        """
        cutoff = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
            days=retention_days
        )
        count = await self.repository.delete_hosts_not_updated_since(cutoff)
        if count:
            logger.info("Purged %d host(s) not updated since %s", count, cutoff)
        else:
            logger.debug("No expired hosts to purge (cutoff=%s)", cutoff)
        return count
