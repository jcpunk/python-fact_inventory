from datetime import datetime

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import select

from .models import HostFacts


class HostFactsRepository(SQLAlchemyAsyncRepository[HostFacts]):  # type: ignore[misc]
    """
    This is the database logic it should have some knowledge of how the
    database is setup, how to query it, and other behaviors that are not
    abstracted away from the db interface.

    It should only have database specific workflows.
    """

    model_type = HostFacts

    async def exists_recent_for_client(
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
