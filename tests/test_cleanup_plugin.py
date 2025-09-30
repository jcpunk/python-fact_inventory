"""
Tests for the DailyCleanupPlugin.
"""

import asyncio
import contextlib
from unittest.mock import MagicMock

import pytest
from app.cleanup import DailyCleanupPlugin
from litestar.config.app import AppConfig

_ONE_DAY_SECONDS = 86_400
_ONE_HOUR_SECONDS = 3600
_DEFAULT_JITTER_SECONDS = 1200
_CUSTOM_JITTER_SECONDS = 600
_MIN_INTERVAL_SECONDS = 60
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
            cleanup_fn=_noop,
            interval_seconds=_ONE_HOUR_SECONDS,
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

    def test_rejects_interval_below_minimum(self) -> None:
        """interval_seconds below the minimum must raise ValueError."""

        async def _noop() -> None: ...

        with pytest.raises(ValueError, match="interval_seconds must be"):
            DailyCleanupPlugin(
                cleanup_fn=_noop,
                interval_seconds=_MIN_INTERVAL_SECONDS - 1,
            )

    def test_accepts_minimum_interval(self) -> None:
        """Exactly the minimum interval must be accepted."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(
            cleanup_fn=_noop,
            interval_seconds=_MIN_INTERVAL_SECONDS,
        )
        assert plugin._interval == _MIN_INTERVAL_SECONDS

    def test_default_jitter(self) -> None:
        """Default jitter must be 1200 seconds (20 minutes)."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        assert plugin._jitter == _DEFAULT_JITTER_SECONDS

    def test_custom_jitter(self) -> None:
        """A custom jitter value must be honoured."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(
            cleanup_fn=_noop,
            jitter_seconds=_CUSTOM_JITTER_SECONDS,
        )
        assert plugin._jitter == _CUSTOM_JITTER_SECONDS

    def test_zero_jitter_accepted(self) -> None:
        """jitter_seconds=0 must disable jitter."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop, jitter_seconds=0)
        assert plugin._jitter == 0

    def test_negative_jitter_rejected(self) -> None:
        """Negative jitter_seconds must raise ValueError."""

        async def _noop() -> None: ...

        with pytest.raises(ValueError, match="jitter_seconds must be"):
            DailyCleanupPlugin(cleanup_fn=_noop, jitter_seconds=-1)


class TestDailyCleanupPluginOnAppInit:
    """Tests for the on_app_init hook."""

    def test_registers_lifespan_hook(self) -> None:
        """on_app_init must append to the lifespan list."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        config = AppConfig()
        original_len = len(config.lifespan)

        plugin.on_app_init(config)

        assert len(config.lifespan) == original_len + 1

    def test_returns_app_config(self) -> None:
        """on_app_init must return the (possibly mutated) AppConfig."""

        async def _noop() -> None: ...

        plugin = DailyCleanupPlugin(cleanup_fn=_noop)
        config = AppConfig()

        result = plugin.on_app_init(config)

        assert result is config


class TestDailyCleanupPluginLifecycle:
    """Tests for the lifespan-managed lifecycle."""

    async def test_lifespan_creates_and_cancels_task(self) -> None:
        """The lifespan context manager must manage a task."""
        called = asyncio.Event()

        async def _signal() -> None:
            called.set()

        plugin = DailyCleanupPlugin(
            cleanup_fn=_signal,
            interval_seconds=_MIN_INTERVAL_SECONDS,
            name="test-lifecycle",
        )
        mock_app = MagicMock()

        async with plugin._lifespan(mock_app):
            tasks = [t for t in asyncio.all_tasks() if t.get_name() == "test-lifecycle"]
            assert len(tasks) == 1

        # After exiting the context manager, task should be done
        assert tasks[0].done()

    async def test_cleanup_fn_is_called(self) -> None:
        """The cleanup function must be called after the interval."""
        called = asyncio.Event()

        async def _signal() -> None:
            called.set()

        plugin = DailyCleanupPlugin(
            cleanup_fn=_signal,
            interval_seconds=_MIN_INTERVAL_SECONDS,
            name="test-call",
        )
        # Override interval and jitter for fast test execution
        plugin._interval = 0
        plugin._jitter = 0
        mock_app = MagicMock()

        async with plugin._lifespan(mock_app):
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(called.wait(), timeout=2.0)

        assert called.is_set()

    async def test_loop_survives_cleanup_exception(self) -> None:
        """An exception in the cleanup fn must not kill the loop."""
        call_count = 0

        async def _failing() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "boom"
                raise RuntimeError(msg)

        plugin = DailyCleanupPlugin(
            cleanup_fn=_failing,
            interval_seconds=_MIN_INTERVAL_SECONDS,
            name="test-survive",
        )
        # Override interval and jitter for fast test execution
        plugin._interval = 0
        plugin._jitter = 0
        mock_app = MagicMock()

        async with plugin._lifespan(mock_app):
            await asyncio.sleep(0.1)

        assert call_count >= _MIN_EXPECTED_CALLS, (
            f"Expected >={_MIN_EXPECTED_CALLS} calls, got {call_count}"
        )
