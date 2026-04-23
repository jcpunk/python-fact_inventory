"""Tests for time-based and history-based retention policies."""

from datetime import UTC, datetime, timedelta

import pytest
from fact_inventory.domain.retention import (
    HistoryRetentionPolicy,
    TimeRetentionPolicy,
)


class TestTimeRetentionPolicy:
    def test_validation_bounds(self) -> None:
        TimeRetentionPolicy(days=1)
        TimeRetentionPolicy(days=3650)
        with pytest.raises(ValueError):
            TimeRetentionPolicy(days=0)
        with pytest.raises(ValueError):
            TimeRetentionPolicy(days=-1)
        with pytest.raises(ValueError):
            TimeRetentionPolicy(days=3651)

    def test_cutoff_is_in_the_past(self) -> None:
        assert TimeRetentionPolicy(days=30).cutoff_datetime < datetime.now(tz=UTC)

    def test_cutoff_is_approximately_n_days_ago(self) -> None:
        policy = TimeRetentionPolicy(days=30)
        delta = datetime.now(tz=UTC) - policy.cutoff_datetime
        assert abs(delta - timedelta(days=30)) < timedelta(seconds=1)

    def test_cutoff_one_day_is_approximately_24h_ago(self) -> None:
        policy = TimeRetentionPolicy(days=1)
        delta = datetime.now(tz=UTC) - policy.cutoff_datetime
        assert abs(delta - timedelta(days=1)) < timedelta(seconds=1)

    def test_repr(self) -> None:
        assert "30" in repr(TimeRetentionPolicy(days=30))


class TestHistoryRetentionPolicy:
    def test_validation_bounds(self) -> None:
        HistoryRetentionPolicy(max_entries=1)
        HistoryRetentionPolicy(max_entries=1000)
        with pytest.raises(ValueError):
            HistoryRetentionPolicy(max_entries=0)
        with pytest.raises(ValueError):
            HistoryRetentionPolicy(max_entries=-1)
        with pytest.raises(ValueError):
            HistoryRetentionPolicy(max_entries=1001)

    def test_repr(self) -> None:
        assert "50" in repr(HistoryRetentionPolicy(max_entries=50))
