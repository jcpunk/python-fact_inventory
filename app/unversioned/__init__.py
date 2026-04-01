"""Unversioned operational endpoints (health, readiness probes).

Import handlers from this package directly::

    from app.unversioned import health_check, ready_check
"""

from .health import health_check
from .ready import ready_check

__all__ = ["health_check", "ready_check"]
