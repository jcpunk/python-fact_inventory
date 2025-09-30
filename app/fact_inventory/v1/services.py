import datetime
from typing import Any

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ...settings import RATE_LIMIT_MINUTES
from ..schemas.hostfacts import HostFacts, HostFactsRepository


class HostFactsService(SQLAlchemyAsyncRepositoryService[HostFacts]):  # type: ignore[misc]
    """
    This is the "business logic" for our object.

    It should not have any database specific calls, logic, or workflows.
    """

    model_type = HostFacts
    repository_type = HostFactsRepository

    async def rate_limit_exceeded(self, client_address: str) -> bool:
        threshold = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
            minutes=RATE_LIMIT_MINUTES
        )
        return await self.repository.exists_recent_update_for_client(  # type: ignore[no-any-return]
            client_address, threshold
        )

    async def save_client(self, data: dict[str, Any]) -> None:
        await self.upsert(  # technically this is a bit database specific
            data=data,
            match_fields=["client_address"],  # tells it how to detect duplicates
            auto_commit=True,
        )
