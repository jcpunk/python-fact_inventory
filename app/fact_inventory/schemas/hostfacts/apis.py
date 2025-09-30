"""
We store our api schemas here
"""

import json
from typing import Any

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from pydantic import field_validator

from .models import HostFacts


class HostFactsWriteAPI(SQLAlchemyDTO[HostFacts]):  # type: ignore[misc]
    """What API endpoints should HostFacts expose for writing"""

    config = SQLAlchemyDTOConfig(
        exclude={
            "id",
            "created_at",
            "updated_at",
            "client_address",
        },  # Client doesn't provide these
        forbid_unknown_fields=True,  # Error out on unknown/extra fields
    )

    @field_validator("system_facts", "package_facts")  # type: ignore[misc]
    @classmethod
    def validate_json_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        # https://github.com/orgs/litestar-org/discussions/4351
        json_str = json.dumps(v)
        max_size_bytes = 1024 * 1024 * 4  # This hard coded value is guess work

        if len(json_str.encode("utf-8")) > max_size_bytes:
            raise ValueError(  # noqa: TRY003
                f"JSON field exceeds maximum size of {max_size_bytes} bytes"
            )

        return v
