"""
Tests for the retention module.
"""

from unittest.mock import patch

from app.fact_inventory.retention import _is_postgresql, start_retention_task


class TestRetentionHelpers:
    """Tests for retention utility functions."""

    def test_is_postgresql_with_postgresql_uri(self) -> None:
        """Test that _is_postgresql returns True for PostgreSQL URIs."""
        with patch("app.fact_inventory.retention.DATABASE_URI", "postgresql+asyncpg://user:pass@localhost/db"):
            assert _is_postgresql() is True

    def test_is_postgresql_with_postgres_uri(self) -> None:
        """Test that _is_postgresql returns True for postgres:// URIs."""
        with patch("app.fact_inventory.retention.DATABASE_URI", "postgres://user:pass@localhost/db"):
            assert _is_postgresql() is True

    def test_is_postgresql_with_sqlite_uri(self) -> None:
        """Test that _is_postgresql returns False for SQLite URIs."""
        with patch("app.fact_inventory.retention.DATABASE_URI", "sqlite+aiosqlite:///:memory:"):
            assert _is_postgresql() is False

    def test_start_retention_task_disabled(self) -> None:
        """Test that start_retention_task returns None when retention is disabled."""
        with patch("app.fact_inventory.retention.RETENTION_DAYS", 0):
            result = start_retention_task()
            assert result is None

    def test_start_retention_task_non_postgresql(self) -> None:
        """Test that start_retention_task returns None for non-PostgreSQL databases."""
        with (
            patch("app.fact_inventory.retention.RETENTION_DAYS", 90),
            patch("app.fact_inventory.retention.DATABASE_URI", "sqlite+aiosqlite:///:memory:"),
        ):
            result = start_retention_task()
            assert result is None
