"""Litestar plugins provided by the fact_inventory sub-application.

Plugins use the ``InitPluginProtocol`` so that the sub-application owns its
full lifecycle and remains portable across host applications.
"""

from .cleanup import DailyCleanupPlugin

__all__ = ["DailyCleanupPlugin"]
