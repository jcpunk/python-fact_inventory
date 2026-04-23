"""Response models for API endpoints.

Defines unified response envelopes used across all API endpoints (versioned and
unversioned). Provides a consistent structure for success, error, and status responses.

Notes
-----
APIResponse is the unified response envelope model used across all API endpoints.

All API responses follow this structure:
    {
        "status": Literal["ok" | "error"],
        "detail": str,
        "data": dict | None
    }
"""

from typing import Any, Literal

from pydantic import BaseModel

__all__ = ["APIResponse"]


class APIResponse(BaseModel):
    """Unified response envelope for all API endpoints.

    All API responses (success, error, status) use this envelope to provide
    consistent structure across versioned and unversioned endpoints.

    Attributes
    ----------
    status : Literal["ok", "error"]
        Response status indicator.
        - "ok": Successful operation that returns existing state (health, ready)
        - "error": Operation failed (4xx, 5xx status codes)
    detail : str
        Human-readable message describing the result or error. Always present
        in every response.
    data : dict[str, Any] | None
        Optional response data. May contain additional context:
        - For successful operations: endpoint-specific data or `None`
        - For errors: optional error details or `None`

    Examples
    --------
    Success response (resource created):
        {"status": "ok", "detail": "Facts stored successfully for 192.0.2.1",
         "data": None}

    Error response:
        {"status": "error", "detail": "Service unavailable",
         "data": None}
    """

    status: Literal["ok", "error"]
    detail: str
    data: dict[str, Any] | None = None
