import datetime

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
        return await self.repository.exists_recent_for_client(client_address, threshold)  # type: ignore[no-any-return]
