"""Background job scheduler plugin for periodic task execution.

The ``AsyncBackgroundJobPlugin`` implements Litestar's `` InitPlugin`` so it
can wire its own lifecycle hooks through ``on_app_init`` rather than requiring
the host application to manage background tasks directly.

Notes
-----
- Uses Litestar's ``lifespan`` hook; startup and shutdown are self-contained.
- The first job run is deferred until after the initial sleep, avoiding latency.
- Exceptions are logged; the plugin retries on the next interval, enabling diagnosis.
- Configurable jitter (~20 min) avoids jobs firing at the same wall-clock time each day.
- The job returns record count; the plugin logs duration and metadata.

Why not ``BackgroundTask``?
---------------------------
``litestar.background_tasks.BackgroundTask`` is designed for **one-shot
tasks triggered after an HTTP response** -- it is tied to the
request/response cycle.  A periodic job must run independently
of requests, so we use an ``asyncio.Task`` managed through the
application lifespan instead.

Multiple Background Jobs
------------------------
Multiple ``AsyncBackgroundJobPlugin`` instances can be configured within
a single application to run different tasks at different intervals.
Each plugin operates independently with its own job callback, schedule,
and logging output. This allows, for example, one plugin to handle
retention-based cleanup while another handles history cleanup.
"""

import asyncio
import contextlib
import logging
import secrets
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from litestar import Litestar
from litestar.config.app import AppConfig
from litestar.plugins import InitPlugin

__all__ = ["AsyncBackgroundJobPlugin"]

_MIN_INTERVAL_SECONDS = 60


class AsyncBackgroundJobPlugin(InitPlugin):
    """Background plugin that runs a scheduled job coroutine once per interval.

    Runs in the application's event loop - safe for async DB calls.
    The first job run is deferred until after the first sleep, avoiding
    startup latency.

    Parameters
    ----------
    job_callback : Callable[..., Coroutine[Any, Any, int]]
        An async callable (no arguments) that performs the job work
        and returns the number of records processed.
    interval_seconds : int, optional
        Seconds between successive runs. Must be >= 60 to prevent
        accidental tight loops. Defaults to 86400 (24 hours).
    jitter_seconds : int, optional
        Maximum random offset (in seconds) added to each sleep cycle.
        Prevents all instances from firing at the exact same time.
        Defaults to 1200 (20 minutes). Set to 0 to disable jitter.
    name : str, optional
        Human-readable label used in log messages and as the
        asyncio.Task name. Defaults to "background-job".

    Raises
    ------
    ValueError
        If interval_seconds is less than 60 or jitter_seconds is negative.
    """

    def __init__(
        self,
        job_callback: Callable[..., Coroutine[Any, Any, int]],
        interval_seconds: int = 86400,
        jitter_seconds: int = 1200,
        name: str = "background-job",
        **kwargs: Any,
    ) -> None:
        if interval_seconds < _MIN_INTERVAL_SECONDS:
            raise ValueError(  # noqa: TRY003
                f"interval_seconds must be >= {_MIN_INTERVAL_SECONDS},"
                f" got {interval_seconds}"
            )
        if jitter_seconds < 0:
            raise ValueError(f"jitter_seconds must be >= 0, got {jitter_seconds}")  # noqa: TRY003

        super().__init__()

        self._job_callback = job_callback
        self._interval = interval_seconds
        self._jitter = jitter_seconds
        self._name = name
        self._callback_kwargs = kwargs

    # ----------------------------------------------------------------------
    # InitPluginProtocol
    # ----------------------------------------------------------------------
    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Attach the scheduled job lifespan hook to the application config.

        Required by InitPluginProtocol. Appends _lifespan to
        app_config.lifespan so Litestar starts the background task when
        the application starts and cancels it on shutdown.

        Parameters
        ----------
        app_config : AppConfig
            The mutable AppConfig passed in by Litestar during
            application assembly.

        Returns
        -------
        AppConfig
            The same app_config object, mutated in place. Returning it
            is required by the InitPluginProtocol contract.
        """
        app_config.lifespan.append(self._lifespan)
        return app_config

    # ----------------------------------------------------------------------
    # Lifespan management
    # ----------------------------------------------------------------------
    @asynccontextmanager
    async def _lifespan(self, _app: Litestar) -> AsyncGenerator[None, None]:
        """Start the scheduled job task on application startup; stop it on shutdown.

        Used as a Litestar lifespan context manager. Creates an
        asyncio.Task wrapping _loop, yields control to the running
        application, then cancels and awaits the task during shutdown to
        ensure a clean exit.

        Parameters
        ----------
        _app : Litestar
            The running Litestar application instance. Not used by
            this plugin but required by the lifespan callable signature.

        Yields
        ------
        None
            Control is yielded to the application for its entire runtime.
            The finally block runs during both normal shutdown and on
            error.

        Notes
        -----
        The task is started immediately when entering the context manager
        and is cancelled when exiting. This ensures the background job
        runs for the entire application lifecycle.
        """
        task = asyncio.create_task(self._loop(), name=self._name)
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # ----------------------------------------------------------------------
    # Periodic loop
    # ----------------------------------------------------------------------
    async def _loop(self) -> None:
        """Run the job callable repeatedly until cancelled.

        This coroutine never returns normally; it runs until cancelled.

        Notes
        -----
        Sleep-first design: Each iteration sleeps before calling the job
        function so that the plugin never adds latency to application startup.
        The first job run therefore happens one full interval (plus jitter)
        after the application starts.

        Jitter: A random offset in [0, jitter_seconds) is added to each sleep
        so that multiple instances in a Kubernetes deployment do not fire
        at exactly the same wall-clock time.

        Exception handling: asyncio.CancelledError is re-raised immediately so
        the task responds correctly to task.cancel() during application shutdown.
        All other exceptions are caught, logged with a full traceback, and
        silently retried on the next interval. This prevents a transient
        database outage from permanently killing the job task.

        Raises
        ------
        asyncio.CancelledError
            When the task is cancelled during application shutdown.
        """
        while True:
            # Sleep first to prevent delaying application startup.
            jitter = secrets.randbelow(int(self._jitter + 1)) if self._jitter else 0
            sleep_time = self._interval + jitter
            await asyncio.sleep(sleep_time)
            try:
                await self._job_callback()
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger(__name__).exception(
                    "Background job failed, rescheduling"
                )
