"""Response models for the v1 API."""

from pydantic import BaseModel


class DetailResponse(BaseModel):
    """Response envelope for v1 endpoints (success and error paths)."""

    detail: str
    """Human-readable message describing the result or error."""
