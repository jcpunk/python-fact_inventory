"""
We store our model schema here
"""

from typing import Any

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import DDL, JSON, Index, String, event, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column


class HostFacts(UUIDAuditBase):
    """
    Database model for storing host information and facts.

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
    See docs/PARTITIONING.md for setup instructions.

    NOTE:
    A stored procedure for data retention is created automatically
    on PostgreSQL when the table is first created.  Schedule it with
    pg_cron as described in docs/RETENTION.md.

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

    system_facts: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        server_default=text("'{}'"),
        nullable=False,
        comment="System facts as JSON",
    )

    package_facts: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        server_default=text("'{}'"),
        nullable=False,
        comment="Package facts as JSON",
    )

    __table_args__ = (
        Index(
            "ix_host_facts_created_at",
            "created_at",
            postgresql_ops={"created_at": "DESC"},  # Used for sorting
        ),
        Index(
            "ix_host_facts_updated_at",
            "updated_at",
            postgresql_ops={"updated_at": "DESC"},  # Used for sorting
        ),
        Index("ix_host_facts_client_address", "client_address"),
        Index(
            "ix_host_facts_client_address_updated_at", "client_address", "updated_at"
        ),
        ## PostgreSQL : GIN indexes for efficient JSON querying
        Index("ix_host_facts_system_facts", "system_facts", postgresql_using="gin"),
        Index("ix_host_facts_package_facts", "package_facts", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return (
            f"<HostFacts client_address={self.client_address}"
            f" created_at={self.created_at}"
            f" updated_at={self.updated_at}>"
        )


# ----------------------------------------------------------------------
# PostgreSQL stored procedure for data retention.
#
# Created automatically alongside the table (via create_all=True).
# The DBA schedules it with pg_cron — see docs/RETENTION.md.
#
# Usage:  SELECT purge_stale_host_facts(90);   -- 90-day retention
# ----------------------------------------------------------------------
_purge_function_ddl = DDL(  # type: ignore[no-untyped-call]
    """
    CREATE OR REPLACE FUNCTION purge_stale_host_facts(retention_days integer)
    RETURNS integer
    LANGUAGE plpgsql
    AS $$
    DECLARE
        deleted integer;
    BEGIN
        DELETE FROM host_facts
         WHERE updated_at < (now() - make_interval(days => retention_days));

        GET DIAGNOSTICS deleted = ROW_COUNT;
        RAISE NOTICE 'purge_stale_host_facts: removed % row(s)', deleted;
        RETURN deleted;
    END;
    $$;
    """
)
event.listen(
    HostFacts.__table__,
    "after_create",
    _purge_function_ddl.execute_if(dialect="postgresql"),
)
