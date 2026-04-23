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
* The cleanup callable returns the number of records purged so the
  plugin can emit a single structured log line per run with duration,
  record count, and the ISO 8601 cutoff date.

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
import time
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
        An async callable (no arguments) that performs the cleanup work
        and returns the number of records purged.
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
        cleanup_fn: Callable[[], Coroutine[Any, Any, int]],
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
        """Attach the cleanup lifespan hook to the application config.

        Required by ``InitPluginProtocol``.  Appends ``_lifespan`` to
        ``app_config.lifespan`` so Litestar starts the background task when
        the application starts and cancels it on shutdown.

        Parameters
        ----------
        app_config:
            The mutable ``AppConfig`` passed in by Litestar during
            application assembly.

        Returns
        -------
        AppConfig
            The same ``app_config`` object, mutated in place.  Returning it
            is required by the ``InitPluginProtocol`` contract.
        """
        app_config.lifespan.append(self._lifespan)
        return app_config

    # ------------------------------------------------------------------
    # Lifespan management
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def _lifespan(self, _app: Litestar) -> AsyncGenerator[None, None]:
        """Start the cleanup task on application startup; stop it on shutdown.

        Used as a Litestar lifespan context manager.  Creates an
        ``asyncio.Task`` wrapping ``_loop``, yields control to the running
        application, then cancels and awaits the task during shutdown to
        ensure a clean exit.

        Parameters
        ----------
        _app:
            The running ``Litestar`` application instance.  Not used by
            this plugin but required by the lifespan callable signature.

        Yields
        ------
        None
            Control is yielded to the application for its entire runtime.
            The ``finally`` block runs during both normal shutdown and on
            error.
        """
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
        """Run the cleanup callable repeatedly until cancelled.

        Sleep-first design
        ~~~~~~~~~~~~~~~~~~
        Each iteration sleeps *before* calling the cleanup function so that
        the plugin never adds latency to application startup.  The first
        cleanup run therefore happens one full interval (plus jitter) after
        the application starts.

        Jitter
        ~~~~~~
        A random offset in ``[0, jitter_seconds)`` is added to each sleep
        so that multiple instances in a Kubernetes deployment do not fire
        at exactly the same wall-clock time.  ``random.uniform`` is used
        rather than ``secrets``-grade randomness because the jitter only
        needs to spread load, not provide security.

        Exception handling
        ~~~~~~~~~~~~~~~~~~
        ``asyncio.CancelledError`` is re-raised immediately so the task
        responds correctly to ``task.cancel()`` during application shutdown.
        All other exceptions are caught, logged with a full traceback, and
        silently retried on the next interval.  This prevents a transient
        database outage from permanently killing the cleanup task.

        This coroutine never returns normally; it runs until cancelled.
        """
        while True:
            # Sleep *first* so we never delay application startup.
            # We don't need strong randomness for the startup jitter.
            # S311 is suppressed accordingly.
            jitter = random.uniform(0, self._jitter) if self._jitter else 0  # noqa: S311
            sleep_time = self._interval + jitter
            await asyncio.sleep(sleep_time)
            logger.info("%s: starting run", self._name)
            start = time.monotonic()
            try:
                records_purged = await self._cleanup_fn()
                duration = time.monotonic() - start
                logger.info(
                    "%s: completed records_purged=%d duration_seconds=%.1f",
                    self._name,
                    records_purged,
                    duration,
                )
            except asyncio.CancelledError:
                raise  # propagate shutdown signal
            except Exception:
                duration = time.monotonic() - start
                logger.exception(
                    "%s: run failed after %.1fs - will retry next interval",
                    self._name,
                    duration,
                )
