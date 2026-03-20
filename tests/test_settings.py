"""Tests for application settings validation."""

import pytest
from app.settings import Settings
from pydantic import ValidationError


class TestSettingsValidation:
    """Tests for Settings field constraints."""

    def test_retention_days_rejects_zero(self) -> None:
        """retention_days must be >= 1."""
        with pytest.raises(ValidationError, match="retention_days"):
            Settings(database_uri="sqlite:///:memory:", retention_days=0)

    def test_retention_days_rejects_negative(self) -> None:
        """retention_days must be >= 1."""
        with pytest.raises(ValidationError, match="retention_days"):
            Settings(database_uri="sqlite:///:memory:", retention_days=-1)

    def test_cleanup_interval_hours_rejects_zero(self) -> None:
        """cleanup_interval_hours must be >= 1."""
        with pytest.raises(ValidationError, match="cleanup_interval_hours"):
            Settings(database_uri="sqlite:///:memory:", cleanup_interval_hours=0)

    def test_rate_limit_max_requests_rejects_zero(self) -> None:
        """rate_limit_max_requests must be >= 1."""
        with pytest.raises(ValidationError, match="rate_limit_max_requests"):
            Settings(database_uri="sqlite:///:memory:", rate_limit_max_requests=0)

    def test_db_pool_size_rejects_zero(self) -> None:
        """db_pool_size must be >= 1."""
        with pytest.raises(ValidationError, match="db_pool_size"):
            Settings(database_uri="sqlite:///:memory:", db_pool_size=0)

    def test_db_pool_max_overflow_accepts_zero(self) -> None:
        """db_pool_max_overflow may be 0 (no overflow connections)."""
        s = Settings(database_uri="sqlite:///:memory:", db_pool_max_overflow=0)
        assert s.db_pool_max_overflow == 0

    def test_db_pool_max_overflow_rejects_negative(self) -> None:
        """db_pool_max_overflow must be >= 0."""
        with pytest.raises(ValidationError, match="db_pool_max_overflow"):
            Settings(database_uri="sqlite:///:memory:", db_pool_max_overflow=-1)

    def test_database_uri_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """database_uri is required and must not be omitted."""
        monkeypatch.delenv("DATABASE_URI", raising=False)
        with pytest.raises(ValidationError, match="database_uri"):
            Settings(_env_file=None)  # type: ignore[call-arg]

    def test_debug_forces_log_level_debug(self) -> None:
        """When debug=True, log_level must be forced to DEBUG."""
        s = Settings(database_uri="sqlite:///:memory:", debug=True)
        assert s.log_level == "DEBUG"

    def test_invalid_rate_limit_unit_rejected(self) -> None:
        """rate_limit_unit must be one of second/minute/hour/day."""
        with pytest.raises(ValidationError, match="rate_limit_unit"):
            Settings(database_uri="sqlite:///:memory:", rate_limit_unit="week")  # type: ignore[arg-type]
