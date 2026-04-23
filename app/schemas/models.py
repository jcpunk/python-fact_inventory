"""Database model for the ``fact_inventory`` table."""

from typing import Any

from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import JsonB
from sqlalchemy import Index, String, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column


class FactInventory(UUIDAuditBase):
    """ORM model for the ``fact_inventory`` table.

    Stores one record per connecting client IP address.  The JSON columns
    hold arbitrary data submitted by the client (for example Ansible
    ``setup`` facts).  See ``docs/VIEWS.md`` for PostgreSQL views that
    project commonly-used JSON keys into queryable columns.

    The primary key is the composite ``(id, client_address)``, where
    ``id`` is a UUID surrogate key provided by ``UUIDAuditBase`` and
    ``client_address`` is the unique business identifier.

    GIN indexes on ``system_facts`` and ``package_facts`` enable
    efficient PostgreSQL JSONB queries but are no-ops on other database
    backends.  Both indexes can be large for deployments with many hosts;
    monitor index size and consider table partitioning for large
    installations.
    """

    __tablename__ = "fact_inventory"

    client_address: Mapped[str] = mapped_column(
        String(45).with_variant(INET, "postgresql"),
        primary_key=True,
        comment="Client IP address (IPv4 or IPv6)",
    )

    system_facts: Mapped[dict[str, Any]] = mapped_column(
        JsonB,
        server_default=text("'{}'"),
        nullable=False,
        comment="System facts as JSON",
    )

    package_facts: Mapped[dict[str, Any]] = mapped_column(
        JsonB,
        server_default=text("'{}'"),
        nullable=False,
        comment="Package facts as JSON",
    )

    local_facts: Mapped[dict[str, Any]] = mapped_column(
        JsonB,
        server_default=text("'{}'"),
        nullable=False,
        comment="Local facts as JSON",
    )

    __table_args__ = (
        Index(
            "ix_fact_inventory_created_at",
            "created_at",
            postgresql_using="brin",
        ),
        Index(
            "ix_fact_inventory_updated_at",
            "updated_at",
        ),
        Index(
            "ix_fact_inventory_client_address_updated_at",
            "client_address",
            "updated_at",
        ),
        # PostgreSQL: GIN indexes for efficient JSON querying
        Index("ix_fact_inventory_system_facts", "system_facts", postgresql_using="gin"),
        Index(
            "ix_fact_inventory_package_facts", "package_facts", postgresql_using="gin"
        ),
        Index("ix_fact_inventory_local_facts", "system_facts", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return (
            f"<FactInventory client_address={self.client_address}"
            f" created_at={self.created_at}"
            f" updated_at={self.updated_at}>"
        )
