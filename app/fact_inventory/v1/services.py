import datetime
import logging
from typing import Any

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ..schemas.hostfacts import HostFacts, HostFactsRepository

logger = logging.getLogger(__name__)


class HostFactsService(SQLAlchemyAsyncRepositoryService[HostFacts]):
    """
    This is the "business logic" for our object.

    It should not have any database specific calls, logic, or workflows.
    """

    model_type = HostFacts
    repository_type = HostFactsRepository
    repository: HostFactsRepository

    async def rate_limit_exceeded(
        self, client_address: str, rate_limit_minutes: int
    ) -> bool:
        """Return True if *client_address* submitted within *rate_limit_minutes*."""
        threshold = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
            minutes=rate_limit_minutes
        )
        return await self.repository.exists_recent_update_for_client(
            client_address, threshold
        )

    async def save_client(self, data: dict[str, Any]) -> None:
        """
        Upsert a fact record, matching on *client_address* to detect and
        replace duplicate hosts.
        """
        await self.upsert(  # technically this is a bit database specific
            data=data,
            match_fields=["client_address"],  # tells it how to detect duplicates
            auto_commit=True,
        )

    async def purge_expired_hosts(self, retention_days: int) -> int:
        """Delete host records not updated within *retention_days*.

        Returns the number of records purged.
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
