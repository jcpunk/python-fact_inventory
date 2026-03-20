"""
Tests for the DailyCleanupPlugin.
"""

import asyncio

from app.fact_inventory.plugins.cleanup import DailyCleanupPlugin
from litestar.config.app import AppConfig

_ONE_DAY_SECONDS = 86_400
_ONE_HOUR_SECONDS = 3600
_MIN_EXPECTED_CALLS = 2


class TestDailyCleanupPluginInit:
    """Tests for DailyCleanupPlugin construction and configuration."""

    def test_stores_cleanup_fn(self) -> None:
        """The plugin must store the provided cleanup callable."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        assert plugin._cleanup_fn is _noop

    def test_default_interval_is_one_day(self) -> None:
        """Default interval must be 86 400 seconds (24 hours)."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        assert plugin._interval == _ONE_DAY_SECONDS

    def test_custom_interval(self) -> None:
        """A custom interval must be honoured."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(
            cleanup_fn=_noop, interval_seconds=_ONE_HOUR_SECONDS
        )
        assert plugin._interval == _ONE_HOUR_SECONDS

    def test_default_name(self) -> None:
        """Default name must be 'daily-cleanup'."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        assert plugin._name == "daily-cleanup"

    def test_custom_name(self) -> None:
        """A custom name must be honoured."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop, name="my-job")
        assert plugin._name == "my-job"

    def test_task_initially_none(self) -> None:
        """The background task must be None before startup."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        assert plugin._task is None


class TestDailyCleanupPluginOnAppInit:
    """Tests for the on_app_init hook."""

    def test_registers_startup_hook(self) -> None:
        """on_app_init must append to on_startup."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        config = AppConfig()
        original_len = len(config.on_startup)

        plugin.on_app_init(config)

        assert len(config.on_startup) == original_len + 1

    def test_registers_shutdown_hook(self) -> None:
        """on_app_init must append to on_shutdown."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        config = AppConfig()
        original_len = len(config.on_shutdown)

        plugin.on_app_init(config)

        assert len(config.on_shutdown) == original_len + 1

    def test_returns_app_config(self) -> None:
        """on_app_init must return the (possibly mutated) AppConfig."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        config = AppConfig()

        result = plugin.on_app_init(config)

        assert result is config


class TestDailyCleanupPluginLifecycle:
    """Tests for the start / stop / loop lifecycle."""

    async def test_start_creates_task(self) -> None:
        """_start must create an asyncio.Task."""
        call_count = 0

        async def _counting() -> None:
            nonlocal call_count
            call_count += 1

        plugin = DailyCleanupPlugin(
            cleanup_fn=_counting, interval_seconds=1, name="test-start"
        )
        await plugin._start()

        assert plugin._task is not None
        assert not plugin._task.done()

        # Clean up
        await plugin._stop()

    async def test_stop_cancels_task(self) -> None:
        """_stop must cancel the running task cleanly."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(
            cleanup_fn=_noop, interval_seconds=1, name="test-stop"
        )
        await plugin._start()
        assert plugin._task is not None

        await plugin._stop()

        assert plugin._task.done()

    async def test_stop_noop_when_no_task(self) -> None:
        """_stop must not raise when called before _start."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        # Must not raise
        await plugin._stop()

    async def test_cleanup_fn_is_called(self) -> None:
        """The cleanup function must be called after the sleep interval."""
        called = asyncio.Event()

        async def _signal() -> None:
            called.set()

        plugin = DailyCleanupPlugin(
            cleanup_fn=_signal, interval_seconds=0, name="test-call"
        )
        await plugin._start()

        # Wait briefly for the async loop to fire
        try:
            await asyncio.wait_for(called.wait(), timeout=2.0)
        finally:
            await plugin._stop()

        assert called.is_set()

    async def test_loop_survives_cleanup_exception(self) -> None:
        """An exception in the cleanup function must not kill the loop."""
        call_count = 0

        async def _failing() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "boom"
                raise RuntimeError(msg)

        plugin = DailyCleanupPlugin(
            cleanup_fn=_failing, interval_seconds=0, name="test-survive"
        )
        await plugin._start()

        # Give the loop time to run twice
        await asyncio.sleep(0.1)
        await plugin._stop()

        assert call_count >= _MIN_EXPECTED_CALLS, (
            f"Expected >={_MIN_EXPECTED_CALLS} calls, got {call_count}"
        )
