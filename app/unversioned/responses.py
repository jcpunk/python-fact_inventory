"""Shared response dataclasses for unversioned operational endpoints."""

from dataclasses import dataclass


@dataclass
class ServiceStatusResponse:
    """Response body returned by liveness and readiness probes."""

    status: str
    service: str


@dataclass
class ErrorDetail:
    """Response body returned when a probe detects a failure."""

    detail: str
