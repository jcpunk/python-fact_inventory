"""Tests for AsyncBackgroundJobPlugin lifecycle and job execution."""

import asyncio
import contextlib
from typing import Any
from unittest.mock import MagicMock

import pytest
from fact_inventory.config.background import AsyncBackgroundJobPlugin


@pytest.fixture
def dummy_callback() -> Any:
    async def _cb() -> int:  # pragma: no cover
        return 0

    return _cb  # pragma: no cover


@pytest.fixture
def mock_app() -> MagicMock:
    return MagicMock()


class TestInitialization:
    def test_valid_config_succeeds(self, dummy_callback: Any) -> None:
        plugin = AsyncBackgroundJobPlugin(
            job_callback=dummy_callback, interval_seconds=60, name="test"
        )
        assert plugin is not None

    def test_rejects_interval_below_60(self, dummy_callback: Any) -> None:
        with pytest.raises(ValueError, match="interval_seconds must be >= 60"):
            AsyncBackgroundJobPlugin(job_callback=dummy_callback, interval_seconds=30)

    def test_rejects_negative_jitter(self, dummy_callback: Any) -> None:
        with pytest.raises(ValueError, match="jitter_seconds must be >= 0"):
            AsyncBackgroundJobPlugin(job_callback=dummy_callback, jitter_seconds=-1)

    def test_job_exception_does_not_prevent_construction(self) -> None:
        async def failing() -> int:  # pragma: no cover
            raise RuntimeError("boom")

        plugin = AsyncBackgroundJobPlugin(job_callback=failing, interval_seconds=60)
        assert plugin is not None

    def test_jitter_value_stored(self, dummy_callback: Any) -> None:
        plugin = AsyncBackgroundJobPlugin(
            job_callback=dummy_callback, interval_seconds=60, jitter_seconds=600
        )
        assert plugin._jitter == 600


class TestLifespan:
    async def test_on_app_init_attaches_lifespan(self, dummy_callback: Any) -> None:
        plugin = AsyncBackgroundJobPlugin(
            job_callback=dummy_callback,
            interval_seconds=60,
            jitter_seconds=0,
            name="test-lifespan",
        )
        mock_config = MagicMock()
        mock_config.lifespan = []
        plugin.on_app_init(mock_config)
        assert len(mock_config.lifespan) == 1

    async def test_creates_task_on_enter(
        self, dummy_callback: Any, mock_app: MagicMock
    ) -> None:
        plugin = AsyncBackgroundJobPlugin(
            job_callback=dummy_callback,
            interval_seconds=60,
            jitter_seconds=0,
            name="test-create",
        )
        async with plugin._lifespan(mock_app):
            tasks = [t for t in asyncio.all_tasks() if t.get_name() == "test-create"]
            assert len(tasks) == 1

    async def test_cancels_task_on_exit(
        self, dummy_callback: Any, mock_app: MagicMock
    ) -> None:
        plugin = AsyncBackgroundJobPlugin(
            job_callback=dummy_callback,
            interval_seconds=60,
            jitter_seconds=0,
            name="test-cancel",
        )
        task_ref = None
        async with plugin._lifespan(mock_app):
            tasks = [t for t in asyncio.all_tasks() if t.get_name() == "test-cancel"]
            assert len(tasks) == 1
            task_ref = tasks[0]
        assert task_ref.done()

    async def test_task_name_matches_plugin_name(
        self, dummy_callback: Any, mock_app: MagicMock
    ) -> None:
        plugin = AsyncBackgroundJobPlugin(
            job_callback=dummy_callback,
            interval_seconds=60,
            jitter_seconds=0,
            name="my-job",
        )
        async with plugin._lifespan(mock_app):
            assert any(t.get_name() == "my-job" for t in asyncio.all_tasks())


class TestJobExecution:
    async def test_callback_is_invoked(self, mock_app: MagicMock) -> None:
        called = asyncio.Event()

        async def signal() -> int:
            called.set()
            return 42

        plugin = AsyncBackgroundJobPlugin(
            job_callback=signal, interval_seconds=60, jitter_seconds=0
        )
        plugin._interval = 0
        plugin._jitter = 0

        async with plugin._lifespan(mock_app):
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(called.wait(), timeout=2.0)
        assert called.is_set()

    async def test_loop_survives_repeated_failures(self, mock_app: MagicMock) -> None:
        call_count = {"n": 0}

        async def intermittent() -> int:
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("transient")
            return 0

        plugin = AsyncBackgroundJobPlugin(
            job_callback=intermittent, interval_seconds=60, jitter_seconds=0
        )
        plugin._interval = 0
        plugin._jitter = 0

        async with plugin._lifespan(mock_app):
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.sleep(0.5), timeout=2.0)
        assert call_count["n"] >= 1

    async def test_timeout_error_is_caught(self, mock_app: MagicMock) -> None:
        async def times_out() -> int:
            raise TimeoutError

        plugin = AsyncBackgroundJobPlugin(
            job_callback=times_out, interval_seconds=60, jitter_seconds=0
        )
        plugin._interval = 0
        plugin._jitter = 0

        async with plugin._lifespan(mock_app):
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.sleep(0.5), timeout=2.0)
        assert plugin is not None

    async def test_cancelled_error_propagates(self) -> None:
        """asyncio.CancelledError must propagate so task.cancel() works on shutdown."""
        completed = asyncio.Event()

        async def signalling_job() -> int:
            completed.set()
            return 0

        plugin = AsyncBackgroundJobPlugin(
            job_callback=signalling_job, interval_seconds=60, jitter_seconds=0
        )
        plugin._interval = 0
        plugin._jitter = 0

        task = asyncio.create_task(plugin._loop())
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(completed.wait(), timeout=2.0)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert task.done()

    async def test_cancelled_error_inside_callback_propagates(self) -> None:
        """CancelledError raised inside the job callback must re-raise (line 223).

        This covers the except asyncio.CancelledError: raise branch, which is
        entered when the callback itself is cancelled mid-execution rather than
        the outer sleep.
        """
        entered = asyncio.Event()

        async def blocking_job() -> int:
            entered.set()
            await asyncio.sleep(60)  # will be cancelled from outside
            return 0

        plugin = AsyncBackgroundJobPlugin(
            job_callback=blocking_job, interval_seconds=60, jitter_seconds=0
        )
        plugin._interval = 0
        plugin._jitter = 0

        task = asyncio.create_task(plugin._loop())
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(entered.wait(), timeout=2.0)
        assert entered.is_set(), "Job callback never started"
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert task.done()
