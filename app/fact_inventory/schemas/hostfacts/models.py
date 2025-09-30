"""
We store our model schema here
"""

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import JSON, Index, String, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column


class HostFacts(UUIDAuditBase):  # type: ignore[misc]
    """
    Database model for storing host information and facts.

    This table stores JSON data (collected from Ansible facts).

    Indexing the JSON fields is difficult in a general purpose engine.
    There are database specific indexes you could apply to JSON objects.
    However, these indexes have non-standard query syntax.

    You may be better off creating a virtual table/view with the parts
    you intend to use.

    This model is optimized for use with PostgreSQL and will create
    an index on the system_facts JSON. This index is useless on other
    database backends but permits PostgreSQL specific JSON query syntax.

    NOTE:
    The index on system_facts is enormous!

    NOTE:
    This table will grow a lot in size and should be partitioned.
    This management task is left to your DBA.

    Attributes:
        created_at: Timestamp when the record was created
        updated_at: Timestamp when the record was modified
        client_address: IP address of the submitting host (IPv4/IPv6)
        system_facts: JSON object containing system facts
        package_facts: JSON object containing package facts
    """

    __tablename__ = "host_facts"

    client_address: Mapped[str] = mapped_column(
        String(45).with_variant(INET, "postgresql"),
        nullable=False,
        unique=True,
        comment="Client IP address (IPv4 or IPv6)",
    )

    system_facts: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        server_default=text("'{}'"),
        nullable=False,
        comment="System facts as JSON",
    )

    package_facts: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        server_default=text("'{}'"),
        nullable=False,
        comment="Package facts as JSON",
    )

    __table_args__ = (
        Index(
            "ix_host_info_created_at",
            "created_at",
            postgresql_ops={"created_at": "DESC"},  # Used for sorting
        ),
        Index(
            "ix_host_info_updated_at",
            "updated_at",
            postgresql_ops={"updated_at": "DESC"},  # Used for sorting
        ),
        Index("ix_host_info_client_address", "client_address"),
        ## PostgreSQL : GIN indexes for efficient JSON querying
        Index("ix_host_info_system_facts", "system_facts", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return (
            f"<HostFacts client_address={self.client_address} "
            f"created_at={self.created_at}>"
        )
