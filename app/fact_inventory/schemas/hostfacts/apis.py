"""Pydantic/SQLAlchemy DTO schemas exposed by the fact_inventory API."""

import json
from typing import Any

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from pydantic import field_validator

from ...constants import MAX_JSON_FIELD_BYTES
from .models import HostFacts


class _FieldSizeError(ValueError):
    """Raised when a JSON field exceeds the maximum permitted byte size."""

    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"JSON field exceeds maximum size of {max_bytes} bytes")


class HostFactsWriteAPI(SQLAlchemyDTO[HostFacts]):
    """DTO that exposes only the writable fields of HostFacts to API consumers."""

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
        """Reject any JSON field whose UTF-8 size exceeds MAX_JSON_FIELD_BYTES.

        See https://github.com/orgs/litestar-org/discussions/4351 for background.
        """
        if len(json.dumps(v).encode("utf-8")) > MAX_JSON_FIELD_BYTES:
            raise _FieldSizeError(MAX_JSON_FIELD_BYTES)
        return v
