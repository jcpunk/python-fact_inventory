"""Write DTO for the fact inventory API.

Notes
-----
FactInventoryWriteAPI is the SQLAlchemy DTO for write operations.

SQLAlchemyDTO from advanced_alchemy automatically handles column mapping.
Unknown fields are rejected to ensure clients send only supported data.

Per-field JSON size validation is performed in the service layer (via
JSONFieldSizeConstraint in the domain layer), not at the DTO layer. The
controller catches ValueError raised for oversized fields and converts
it to HTTP 413.
"""

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig

from fact_inventory.infrastructure.db.models import FactInventory

__all__ = ["FactInventoryWriteAPI"]


class FactInventoryWriteAPI(SQLAlchemyDTO[FactInventory]):
    """Write DTO for FactInventory.

    Exposes only system_facts, package_facts, and local_facts for write operations.
    The fields id, created_at, updated_at, and client_address are excluded as they
    are set server-side and must not be supplied by the caller. Unknown fields are
    rejected outright.
    """

    config = SQLAlchemyDTOConfig(
        exclude={"id", "created_at", "updated_at", "client_address"},
        forbid_unknown_fields=True,
    )
