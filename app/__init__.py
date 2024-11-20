"""
Top level application setup
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from litestar import Controller, Litestar, Request, Response, Router, post
from litestar.contrib.sqlalchemy.base import UUIDBase
from litestar.contrib.sqlalchemy.plugins import AsyncSessionConfig, SQLAlchemyAsyncConfig, SQLAlchemyPlugin
from sqlalchemy import DateTime, Index, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

RUNTIME_ENVIRONMENT = os.getenv("RUNTIME", "testing")
TRUE_VALUES = {"TRUE", "True", "true", "YES", "Yes", "yes", "Y", "y", "1"}

# Read in environment specific values
ENV_FILE = Path(f"{os.curdir}/.env.{RUNTIME_ENVIRONMENT}")
if ENV_FILE.is_file():
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE, override=True)


class HostInfo(UUIDBase):
    """
    This class will store information about hosts.
    """

    __tablename__ = "host_info"

    client_address: Mapped[str] = mapped_column(String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    system_facts: Mapped[dict] = mapped_column(default={}, nullable=False)
    package_facts: Mapped[dict] = mapped_column(default={}, nullable=False)

    __table_args__ = (
        Index("ix_host_info_client_address", "client_address"),
        Index("ix_host_info_created_at", "created_at"),
        Index("ix_host_info_system_facts", "system_facts", postgresql_using="gin"),
        Index("ix_host_info_package_facts", "package_facts", postgresql_using="gin"),
    )


class AnsibleFactController(Controller):
    """
    actions taken on ansible related data/facts
    """

    path = "/ansible"

    @post(path="/json")
    async def store_json_facts(self, request: Request, db_session: AsyncSession) -> Response:
        """
        Store the json in the database, return something useful about what we stored
        """
        time_threshold = datetime.now(tz=timezone.utc) - timedelta(minutes=23)
        client_address = request.client.host
        form_data = await request.json()

        try:
            async with db_session.begin():
                result = await db_session.execute(
                    select(HostInfo).filter(
                        HostInfo.client_address == client_address,
                        HostInfo.created_at >= time_threshold,
                    )
                )
                if result.scalars().first():
                    return Response(
                        f"{client_address} has checked in too recently.\n",
                        status_code=425,
                    )

                db_session.add(
                    HostInfo(
                        client_address=client_address,
                        system_facts=form_data.get("system_facts", {}),
                        package_facts=form_data.get("package_facts", {}),
                    )
                )

        except Exception:  # noqa:BLE001
            return Response(f"Unable to save record for {client_address}\n", status_code=409)

        return Response(f"Form submitted successfully for {client_address}\n", status_code=200)


SQLALCHEMY_CONFIG = SQLAlchemyAsyncConfig(
    connection_string=os.getenv("DATABASE_URL"),
    session_config=AsyncSessionConfig(expire_on_commit=False),
    create_all=True,
)

LITESTAR_ARGS = {}
LITESTAR_ARGS["route_handlers"] = [Router(path="/store", route_handlers=[AnsibleFactController])]
LITESTAR_ARGS["plugins"] = [SQLAlchemyPlugin(config=SQLALCHEMY_CONFIG)]
if os.getenv("LITESTAR_DEBUG", "False") not in TRUE_VALUES:
    LITESTAR_ARGS["openapi_config"] = None

app = Litestar(**LITESTAR_ARGS)
