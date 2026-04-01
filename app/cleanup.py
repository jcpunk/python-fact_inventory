"""Background cleanup plugin for periodic host retention enforcement.

The ``DailyCleanupPlugin`` implements Litestar's ``InitPluginProtocol`` so it
can wire its own lifecycle hooks through ``on_app_init`` rather than requiring
the host application to manage background tasks directly.

Design rationale
~~~~~~~~~~~~~~~~
* Uses Litestar's ``lifespan`` context-manager hook so startup and
  shutdown are managed in a single, self-contained block.
* The first cleanup run is deferred until *after* the first sleep so the
  plugin never blocks application startup.
* All exceptions inside the cleanup function are logged but do **not**
  crash the loop -- the plugin retries on the next interval.
* A configurable jitter (default ~20 minutes) is added to each sleep
  cycle so that cleanup runs do not fire at the exact same wall-clock
  time every day.

Why not ``BackgroundTask``?
~~~~~~~~~~~~~~~~~~~~~~~~~~~
``litestar.background_tasks.BackgroundTask`` is designed for **one-shot
tasks triggered after an HTTP response** -- it is tied to the
request/response cycle.  A periodic retention job must run independently
of requests, so we use an ``asyncio.Task`` managed through the
application lifespan instead.
"""

import asyncio
import contextlib
import logging
import random
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from litestar import Litestar
from litestar.config.app import AppConfig
from litestar.plugins import InitPluginProtocol

logger = logging.getLogger(__name__)

_MIN_INTERVAL_SECONDS = 60


class DailyCleanupPlugin(InitPluginProtocol):
    """Background plugin that runs a cleanup coroutine once per interval.

    Runs in the application's event loop -- safe for async DB calls.
    The first run is deferred until after the first sleep, avoiding
    startup latency.

    Parameters
    ----------
    cleanup_fn:
        An async callable (no arguments) to invoke on each cycle.
    interval_seconds:
        Seconds between successive runs.  Must be >= 60 to prevent
        accidental tight loops.  Defaults to 86 400 (24 hours).
    jitter_seconds:
        Maximum random offset (in seconds) added to each sleep cycle.
        Prevents all instances from firing at the exact same time.
        Defaults to 1200 (20 minutes).  Set to 0 to disable jitter.
    name:
        Human-readable label used in log messages and as the
        ``asyncio.Task`` name.

    Raises
    ------
    ValueError
        If *interval_seconds* is less than 60 or *jitter_seconds* is
        negative.
    """

    def __init__(
        self,
        cleanup_fn: Callable[[], Coroutine[Any, Any, None]],
        interval_seconds: int = 86_400,
        jitter_seconds: int = 1200,
        name: str = "daily-cleanup",
    ) -> None:
        if interval_seconds < _MIN_INTERVAL_SECONDS:
            msg = (
                f"interval_seconds must be >= {_MIN_INTERVAL_SECONDS},"
                f" got {interval_seconds}"
            )
            raise ValueError(msg)
        if jitter_seconds < 0:
            msg = f"jitter_seconds must be >= 0, got {jitter_seconds}"
            raise ValueError(msg)

        self._cleanup_fn = cleanup_fn
        self._interval = interval_seconds
        self._jitter = jitter_seconds
        self._name = name

    # ------------------------------------------------------------------
    # InitPluginProtocol
    # ------------------------------------------------------------------

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Register a lifespan context manager with the application."""
        app_config.lifespan.append(self._lifespan)
        return app_config

    # ------------------------------------------------------------------
    # Lifespan management
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def _lifespan(self, _app: Litestar) -> AsyncGenerator[None, None]:
        """Manage the background task for the application's lifetime."""
        logger.info(
            "%s: scheduling cleanup every %ds (jitter up to %ds)",
            self._name,
            self._interval,
            self._jitter,
        )
        task = asyncio.create_task(self._loop(), name=self._name)
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            logger.info("%s: stopped", self._name)

    # ------------------------------------------------------------------
    # Periodic loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Infinite loop: sleep then run the cleanup callable."""
        while True:
            # Sleep *first* so we never delay application startup.
            jitter = random.uniform(0, self._jitter) if self._jitter else 0  # noqa: S311
            sleep_time = self._interval + jitter
            await asyncio.sleep(sleep_time)
            logger.info("%s: starting run", self._name)
            try:
                await self._cleanup_fn()
                logger.info("%s: completed successfully", self._name)
            except asyncio.CancelledError:
                raise  # propagate shutdown signal
            except Exception:
                logger.exception(
                    "%s: run failed - will retry next interval",
                    self._name,
                )
