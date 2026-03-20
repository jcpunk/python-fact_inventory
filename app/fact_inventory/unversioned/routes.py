"""
Unversioned operational route handlers for the fact_inventory sub-application.

These handlers are not tied to any API version and are intended for operational
use - e.g. load-balancer health checks and readiness probes.  They are defined
at relative paths (``/health``, ``/ready``) with no prefix so that the host
application controls where they are mounted via a wrapping ``Router``.

Each handler lives in its own module for separation of concerns.  This module
re-exports them for convenience.
"""

from .health import health_check
from .ready import ready_check

__all__ = ["health_check", "ready_check"]
