"""Background cleanup plugin for periodic host retention enforcement.

The ``DailyCleanupPlugin`` implements Litestar's ``InitPluginProtocol`` so it
can wire its own ``on_startup`` / ``on_shutdown`` hooks through ``on_app_init``
rather than requiring the host application to manage background tasks directly.

Usage::

    from litestar import Litestar
    from app.fact_inventory.plugins import DailyCleanupPlugin

    app = Litestar(
        plugins=[
            DailyCleanupPlugin(
                cleanup_fn=purge_expired_sessions,
                interval_seconds=86_400,
                name="session-cleanup",
            ),
        ],
    )

Design rationale
~~~~~~~~~~~~~~~~
* Wired via ``on_app_init`` so the plugin owns its full lifecycle and
  remains portable across Litestar applications.
* The first cleanup run is deferred until *after* the first sleep so the
  plugin never blocks application startup.
* The plugin cancels its task cleanly on shutdown, suppressing
  ``CancelledError`` so the ASGI server can shut down gracefully.
* All exceptions inside the cleanup function are logged but do **not**
  crash the loop — the plugin retries on the next interval.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from litestar import Litestar
from litestar.config.app import AppConfig
from litestar.plugins import InitPluginProtocol

logger = logging.getLogger(__name__)

_MIN_INTERVAL_SECONDS = 60


class DailyCleanupPlugin(InitPluginProtocol):
    """Background plugin that runs a cleanup coroutine once per interval.

    Runs in the application's event loop — safe for async DB calls.
    The first run is deferred until after the first sleep, avoiding
    startup latency.

    Parameters
    ----------
    cleanup_fn:
        An async callable (no arguments) to invoke on each cycle.
    interval_seconds:
        Seconds between successive runs.  Must be >= 60 to prevent
        accidental tight loops.  Defaults to 86 400 (24 hours).
    name:
        Human-readable label used in log messages and as the
        ``asyncio.Task`` name.
    """

    def __init__(
        self,
        cleanup_fn: Callable[[], Coroutine[Any, Any, None]],
        interval_seconds: int = 86_400,
        name: str = "daily-cleanup",
    ) -> None:
        if interval_seconds < _MIN_INTERVAL_SECONDS:
            msg = (
                f"interval_seconds must be >= {_MIN_INTERVAL_SECONDS},"
                f" got {interval_seconds}"
            )
            raise ValueError(msg)

        self._cleanup_fn = cleanup_fn
        self._interval = interval_seconds
        self._name = name
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # InitPluginProtocol
    # ------------------------------------------------------------------

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Register startup / shutdown hooks with the Litestar application."""
        app_config.on_startup.append(self._start)
        app_config.on_shutdown.append(self._stop)
        return app_config

    # ------------------------------------------------------------------
    # Internal lifecycle helpers
    # ------------------------------------------------------------------

    async def _start(self, _app: Litestar | None = None) -> None:
        """Create the background task.  Called by Litestar on startup."""
        logger.info(
            "%s: scheduling cleanup every %ds", self._name, self._interval
        )
        self._task = asyncio.create_task(
            self._loop(), name=self._name
        )

    async def _stop(self, _app: Litestar | None = None) -> None:
        """Cancel the background task.  Called by Litestar on shutdown."""
        if self._task is None or self._task.done():
            logger.debug("%s: no active task to cancel", self._name)
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._task
        logger.info("%s: stopped", self._name)

    async def _loop(self) -> None:
        """Infinite loop: sleep then run the cleanup callable."""
        while True:
            # Sleep *first* so we never delay application startup.
            await asyncio.sleep(self._interval)
            logger.info("%s: starting run", self._name)
            try:
                await self._cleanup_fn()
                logger.info("%s: completed successfully", self._name)
            except asyncio.CancelledError:
                raise  # propagate shutdown signal
            except Exception:
                logger.exception(
                    "%s: run failed — will retry next interval",
                    self._name,
                )
