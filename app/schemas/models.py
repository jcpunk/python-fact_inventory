"""Database model for the ``fact_inventory`` table."""

from typing import Any

from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import JsonB
from sqlalchemy import Index, String, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column


class FactInventory(UUIDAuditBase):
    """
    Database model for storing per-client system and package facts.

    This table stores JSON data (collected from Ansible facts).

    Indexing the JSON fields is difficult in a general purpose engine.
    There are database specific indexes you could apply to JSON objects.
    However, these indexes have non-standard query syntax.

    You may be better off creating a virtual table/view with the parts
    you intend to use.  See docs/VIEWS.md for examples.

    This model is optimized for use with PostgreSQL and will create
    an index on the system_facts and package_facts JSON.

    These indexes are useless on other database backends but permits
    PostgreSQL specific JSON query syntax.

    NOTE:
    The index on system_facts is enormous!
    The index on package_facts is enormous!

    NOTE:
    This table will grow a lot in size and should be partitioned.
    This management task is left to your DBA to design.

    Attributes:
        created_at: Timestamp when the record was created
        updated_at: Timestamp when the record was modified
        client_address: IP address of the submitting client (IPv4/IPv6)
        system_facts: JSON object containing system facts
        package_facts: JSON object containing package facts
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
    )

    def __repr__(self) -> str:
        return (
            f"<FactInventory client_address={self.client_address}"
            f" created_at={self.created_at}"
            f" updated_at={self.updated_at}>"
        )
