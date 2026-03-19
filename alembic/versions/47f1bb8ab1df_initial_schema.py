"""initial schema

Revision ID: 47f1bb8ab1df
Revises:
Create Date: 2026-03-19 20:13:50.752060

"""

from collections.abc import Sequence

import advanced_alchemy.types.datetime
import advanced_alchemy.types.guid
import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "47f1bb8ab1df"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "host_facts",
        sa.Column(
            "client_address",
            sa.String(length=45).with_variant(postgresql.INET(), "postgresql"),
            nullable=False,
            comment="Client IP address (IPv4 or IPv6)",
        ),
        sa.Column(
            "system_facts",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=Text()), "postgresql"
            ),
            server_default=sa.text("'{}'"),
            nullable=False,
            comment="System facts as JSON",
        ),
        sa.Column(
            "package_facts",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=Text()), "postgresql"
            ),
            server_default=sa.text("'{}'"),
            nullable=False,
            comment="Package facts as JSON",
        ),
        sa.Column(
            "id",
            advanced_alchemy.types.guid.GUID(length=16),
            nullable=False,
        ),
        sa.Column("sa_orm_sentinel", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            advanced_alchemy.types.datetime.DateTimeUTC(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            advanced_alchemy.types.datetime.DateTimeUTC(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_host_facts")),
        sa.UniqueConstraint(
            "client_address", name=op.f("uq_host_facts_client_address")
        ),
    )
    op.create_index(
        "ix_host_facts_client_address",
        "host_facts",
        ["client_address"],
        unique=False,
    )
    op.create_index(
        "ix_host_facts_client_address_updated_at",
        "host_facts",
        ["client_address", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_host_facts_created_at",
        "host_facts",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_host_facts_package_facts",
        "host_facts",
        ["package_facts"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_host_facts_system_facts",
        "host_facts",
        ["system_facts"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_host_facts_updated_at",
        "host_facts",
        ["updated_at"],
        unique=False,
        postgresql_ops={"updated_at": "DESC"},
    )

    # Stored procedure for data retention (PostgreSQL only).
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text("""
            CREATE OR REPLACE FUNCTION purge_stale_host_facts(
                retention_days integer
            )
            RETURNS integer
            LANGUAGE plpgsql
            AS $$
            DECLARE
                deleted integer;
            BEGIN
                DELETE FROM host_facts
                 WHERE updated_at < (
                    now() - make_interval(days => retention_days)
                 );

                GET DIAGNOSTICS deleted = ROW_COUNT;
                RAISE NOTICE
                    'purge_stale_host_facts: removed % row(s)',
                    deleted;
                RETURN deleted;
            END;
            $$;
            """)
        )


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "DROP FUNCTION IF EXISTS"
                " purge_stale_host_facts(integer)"
            )
        )
    op.drop_index(
        "ix_host_facts_updated_at",
        table_name="host_facts",
        postgresql_ops={"updated_at": "DESC"},
    )
    op.drop_index(
        "ix_host_facts_system_facts",
        table_name="host_facts",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_host_facts_package_facts",
        table_name="host_facts",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_host_facts_created_at",
        table_name="host_facts",
        postgresql_ops={"created_at": "DESC"},
    )
    op.drop_index(
        "ix_host_facts_client_address_updated_at", table_name="host_facts"
    )
    op.drop_index("ix_host_facts_client_address", table_name="host_facts")
    op.drop_table("host_facts")
