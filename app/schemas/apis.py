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
    """DTO that exposes only the writable fields of FactInventory to API consumers."""

    config = SQLAlchemyDTOConfig(
        exclude={
            "id",
            "created_at",
            "updated_at",
            "client_address",
        },  # Client doesn't provide these
        forbid_unknown_fields=True,  # Error out on unknown/extra fields
    )

    @field_validator("system_facts", "package_facts")
    @classmethod
    def validate_json_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Reject any JSON field whose UTF-8 size exceeds the configured limit.

        The limit is set by MAX_JSON_FIELD_MB (converted to bytes at startup).
        See https://github.com/orgs/litestar-org/discussions/4351 for background.
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
