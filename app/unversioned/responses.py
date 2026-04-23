"""Shared response dataclasses for unversioned operational endpoints."""

from dataclasses import dataclass


@dataclass
class ServiceStatusResponse:
    """Response from health and readiness probes when operational."""

    status: str
    """Always ``"ok"`` when the probe succeeds."""
    service: str
    """Service name (e.g., ``"fact_inventory"``)."""


@dataclass
class ErrorDetail:
    """Response from a probe when a dependency is unreachable."""

    detail: str
    """Human-readable error message."""
