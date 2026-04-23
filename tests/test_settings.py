"""Tests for application settings validation."""

from typing import Any

import pytest
from app.settings import Settings
from pydantic import ValidationError

_DEFAULT_JITTER_MINUTES = 20
_DEFAULT_MAX_JSON_FIELD_MB = 4
_DEFAULT_MAX_REQUEST_BODY_MB = 13


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
        # Pass _env_file via kwargs to bypass the type checker;
        # pydantic-settings accepts this at runtime.
        kwargs: dict[str, Any] = {"_env_file": None}
        with pytest.raises(ValidationError, match="database_uri"):
            Settings(**kwargs)

    def test_debug_forces_log_level_debug(self) -> None:
        """When debug=True, log_level must be forced to DEBUG."""
        s = Settings(database_uri="sqlite:///:memory:", debug=True)
        assert s.log_level == "DEBUG"

    def test_invalid_rate_limit_unit_rejected(self) -> None:
        """rate_limit_unit must be one of second/minute/hour/day."""
        # Intentionally invalid value -- use Any to avoid lying to
        # the type checker about an impossible Literal.
        invalid_unit: Any = "week"
        with pytest.raises(ValidationError, match="rate_limit_unit"):
            Settings(database_uri="sqlite:///:memory:", rate_limit_unit=invalid_unit)

    def test_cleanup_jitter_minutes_accepts_zero(self) -> None:
        """cleanup_jitter_minutes=0 must disable jitter."""
        s = Settings(database_uri="sqlite:///:memory:", cleanup_jitter_minutes=0)
        assert s.cleanup_jitter_minutes == 0

    def test_cleanup_jitter_minutes_rejects_negative(self) -> None:
        """cleanup_jitter_minutes must be >= 0."""
        with pytest.raises(ValidationError, match="cleanup_jitter_minutes"):
            Settings(database_uri="sqlite:///:memory:", cleanup_jitter_minutes=-1)

    def test_cleanup_jitter_minutes_default(self) -> None:
        """Default cleanup_jitter_minutes must be 20."""
        s = Settings(database_uri="sqlite:///:memory:")
        assert s.cleanup_jitter_minutes == _DEFAULT_JITTER_MINUTES

    def test_max_json_field_mb_default(self) -> None:
        """Default max_json_field_mb must be 4."""
        s = Settings(database_uri="sqlite:///:memory:")
        assert s.max_json_field_mb == _DEFAULT_MAX_JSON_FIELD_MB

    def test_max_json_field_mb_rejects_zero(self) -> None:
        """max_json_field_mb must be >= 1."""
        with pytest.raises(ValidationError, match="max_json_field_mb"):
            Settings(database_uri="sqlite:///:memory:", max_json_field_mb=0)

    def test_max_json_field_mb_rejects_negative(self) -> None:
        """max_json_field_mb must be >= 1."""
        with pytest.raises(ValidationError, match="max_json_field_mb"):
            Settings(database_uri="sqlite:///:memory:", max_json_field_mb=-1)

    def test_max_request_body_mb_default(self) -> None:
        """Default max_request_body_mb must be 13."""
        s = Settings(database_uri="sqlite:///:memory:")
        assert s.max_request_body_mb == _DEFAULT_MAX_REQUEST_BODY_MB

    def test_max_request_body_mb_rejects_zero(self) -> None:
        """max_request_body_mb must be >= 1."""
        with pytest.raises(ValidationError, match="max_request_body_mb"):
            Settings(database_uri="sqlite:///:memory:", max_request_body_mb=0)

    def test_max_request_body_mb_rejects_negative(self) -> None:
        """max_request_body_mb must be >= 1."""
        with pytest.raises(ValidationError, match="max_request_body_mb"):
            Settings(database_uri="sqlite:///:memory:", max_request_body_mb=-1)

    def test_max_request_body_mb_must_exceed_double_field_mb(self) -> None:
        """max_request_body_mb must be greater than 2 x max_json_field_mb."""
        with pytest.raises(ValidationError, match="max_request_body_mb"):
            Settings(
                database_uri="sqlite:///:memory:",
                max_json_field_mb=4,
                max_request_body_mb=8,  # equal to 2*4 -- not strictly greater
            )

    def test_max_request_body_mb_accepts_exactly_above_double_field_mb(self) -> None:
        """max_request_body_mb == 2*max_json_field_mb + 1 must be accepted."""
        s = Settings(
            database_uri="sqlite:///:memory:",
            max_json_field_mb=4,
            max_request_body_mb=13,  # 13 > 2*4
        )
        assert s.max_request_body_mb == _DEFAULT_MAX_REQUEST_BODY_MB
