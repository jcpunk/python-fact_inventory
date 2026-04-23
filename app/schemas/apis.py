"""Pydantic/SQLAlchemy DTO schemas exposed by the fact_inventory API."""

import json
from typing import Any

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from pydantic import field_validator

from ..settings import settings
from .models import FactInventory

# Compute once at startup so the validator does not multiply on every call.
_MAX_JSON_FIELD_BYTES: int = settings.max_json_field_mb * 1024 * 1024


class FactInventoryWriteAPI(SQLAlchemyDTO[FactInventory]):
    """Write DTO for :class:`~app.schemas.models.FactInventory`.

    Exposes only ``system_facts``, ``package_facts``, and ``local_facts``.
    The fields ``id``, ``created_at``, ``updated_at``, and
    ``client_address`` are excluded -- they are set server-side and must
    not be supplied by the caller.  Unknown fields are rejected outright.
    """

    config = SQLAlchemyDTOConfig(
        exclude={"id", "created_at", "updated_at", "client_address"},
        forbid_unknown_fields=True,
    )

    @field_validator("system_facts", "package_facts", "local_facts")
    @classmethod
    def validate_json_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Reject a JSON field whose serialised UTF-8 size exceeds the limit.

        The limit is ``MAX_JSON_FIELD_MB`` bytes, evaluated once at startup.
        Validation runs before the record is written to the database so
        oversized payloads are rejected at the HTTP layer without a
        database round-trip.
        """
        max_bytes = _MAX_JSON_FIELD_BYTES
        if len(json.dumps(v).encode("utf-8")) > max_bytes:
            # We want to specify the message here, there is nothing
            # complex to work through.  TRY003 is suppressed accordingly.
            raise ValueError(  # noqa: TRY003
                f"JSON field exceeds maximum size of {max_bytes} bytes"
                f" ({settings.max_json_field_mb} MB)"
            )
        return v
