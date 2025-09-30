"""Response models for the v1 API."""

from pydantic import BaseModel


class DetailResponse(BaseModel):
    """Response envelope returned on both success and error paths."""

    detail: str
