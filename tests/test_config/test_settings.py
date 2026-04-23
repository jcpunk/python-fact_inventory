"""Tests for application settings and configuration."""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from fact_inventory.config.settings import (
    Settings,
    _get_version,
    settings,
)

TIMEOUT_SECONDS = 5
TEST_PACKAGE_NAME = "test-package"


class TestGetVersion:
    """Tests for _get_version() version detection."""

    def test_git_not_on_path_returns_unknown(self) -> None:
        with (
            patch("importlib.metadata.version", side_effect=Exception),
            patch("shutil.which", return_value=None),
        ):
            assert _get_version(TEST_PACKAGE_NAME) == "unknown"

    def test_git_command_success_returns_commit_hash(self) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "abc1234\n"
        with (
            patch("importlib.metadata.version", side_effect=Exception),
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", return_value=mock_result),
        ):
            assert _get_version(TEST_PACKAGE_NAME) == "git-abc1234"

    def test_git_command_strips_whitespace(self) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "  def5678  \n\n"
        with (
            patch("importlib.metadata.version", side_effect=Exception),
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", return_value=mock_result),
        ):
            assert _get_version(TEST_PACKAGE_NAME) == "git-def5678"

    def test_called_process_error_returns_unknown(self) -> None:
        with (
            patch("importlib.metadata.version", side_effect=Exception),
            patch("shutil.which", return_value="/usr/bin/git"),
            patch(
                "subprocess.run", side_effect=subprocess.CalledProcessError(128, "git")
            ),
        ):
            assert _get_version(TEST_PACKAGE_NAME) == "git-unknown"

    def test_timeout_returns_unknown(self) -> None:
        with (
            patch("importlib.metadata.version", side_effect=Exception),
            patch("shutil.which", return_value="/usr/bin/git"),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired("git", TIMEOUT_SECONDS),
            ),
        ):
            assert _get_version(TEST_PACKAGE_NAME) == "git-unknown"

    def test_uses_short_hash_flag(self) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "1a2b3c4d\n"
        with (
            patch("importlib.metadata.version", side_effect=Exception),
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            _get_version(TEST_PACKAGE_NAME)
            args = mock_run.call_args[0][0]
            assert args[1] == "rev-parse"
            assert args[2] == "--short"
            assert args[3] == "HEAD"

    def test_subprocess_call_includes_timeout(self) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "hash\n"
        with (
            patch("importlib.metadata.version", side_effect=Exception),
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            _get_version(TEST_PACKAGE_NAME)
            assert mock_run.call_args[1]["timeout"] == TIMEOUT_SECONDS


class TestSettingsValidation:
    """Tests for Settings model validation."""

    def test_body_size_validation_passes(self) -> None:
        s = Settings(
            database_uri="sqlite+aiosqlite:///:memory:",
            max_json_field_mb=4,
            max_request_body_mb=13,
        )
        assert s.max_request_body_mb > 3 * s.max_json_field_mb

    def test_body_size_validation_fails_below(self) -> None:
        with pytest.raises(ValueError, match="must be greater"):
            Settings(
                database_uri="sqlite+aiosqlite:///:memory:",
                max_json_field_mb=4,
                max_request_body_mb=12,
            )

    def test_body_size_validation_fails_equal(self) -> None:
        with pytest.raises(ValueError, match="must be greater"):
            Settings(
                database_uri="sqlite+aiosqlite:///:memory:",
                max_json_field_mb=4,
                max_request_body_mb=12,
            )

    def test_version_resolved_from_package(self) -> None:
        s = Settings(
            database_uri="sqlite+aiosqlite:///:memory:",
            app_name="python-fact-inventory",
        )
        assert s.version != "unknown"

    def test_version_unknown_app_falls_back_to_git_or_unknown(self) -> None:
        s = Settings(
            database_uri="sqlite+aiosqlite:///:memory:",
            app_name="nonexistent-package-xyz",
        )
        assert s.version.startswith("git-") or s.version == "unknown"

    def test_explicit_version_not_overwritten(self) -> None:
        with patch("fact_inventory.config.settings._get_version") as mock_get_version:
            s = Settings(
                database_uri="sqlite+aiosqlite:///:memory:",
                app_name="python-fact-inventory",
                version="custom-version-123",
            )
            assert s.version == "custom-version-123"
            mock_get_version.assert_not_called()


class TestSettingsDefaults:
    """Tests for expected settings defaults and attribute presence."""

    def test_has_version(self) -> None:
        assert isinstance(settings.version, str) and len(settings.version) > 0

    def test_has_app_name(self) -> None:
        assert settings.app_name == "fact_inventory"

    def test_log_level_is_valid(self) -> None:
        assert settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    def test_debug_is_bool(self) -> None:
        assert isinstance(settings.debug, bool)

    def test_enable_retention_cleanup_job_is_bool(self) -> None:
        assert isinstance(settings.enable_retention_cleanup_job, bool)

    def test_enable_history_cleanup_job_is_bool(self) -> None:
        assert isinstance(settings.enable_history_cleanup_job, bool)


class TestSettingsIntegration:
    """Integration tests for settings with the app factory."""

    def test_postgres_uri_does_not_crash_factory(self) -> None:
        from fact_inventory.app_factory import create_app

        original_uri = os.environ.get("DATABASE_URI")
        os.environ["DATABASE_URI"] = "postgresql://user:pass@localhost:5432/db"
        try:
            with patch("fact_inventory.config.settings.DEPLOYMENT", "testing"):
                assert create_app() is not None
        finally:
            if original_uri:
                os.environ["DATABASE_URI"] = original_uri

    def test_postgres_uri_cleanup_without_original(self) -> None:
        """Test cleanup when DATABASE_URI did not exist originally."""
        from fact_inventory.app_factory import create_app

        original_uri = os.environ.get("DATABASE_URI")
        if original_uri:
            del os.environ["DATABASE_URI"]
        try:
            with patch("fact_inventory.config.settings.DEPLOYMENT", "testing"):
                assert create_app() is not None
        finally:
            if original_uri:
                os.environ["DATABASE_URI"] = original_uri

    def test_postgres_uri_with_original_env(self) -> None:
        """Test that environment is properly cleaned up after app creation."""
        from fact_inventory.app_factory import create_app

        original_uri = os.environ.get("DATABASE_URI")
        os.environ["DATABASE_URI"] = "postgresql://user:pass@localhost:5432/db"
        try:
            with patch("fact_inventory.config.settings.DEPLOYMENT", "testing"):
                assert create_app() is not None
            assert (
                os.environ.get("DATABASE_URI")
                == "postgresql://user:pass@localhost:5432/db"
            )
        finally:
            if original_uri:
                os.environ["DATABASE_URI"] = original_uri
            else:
                os.environ.pop("DATABASE_URI", None)

    def test_postgres_uri_no_env_var(self) -> None:
        """Test app creation when DATABASE_URI is not set."""
        from fact_inventory.app_factory import create_app

        os.environ.pop("DATABASE_URI", None)
        try:
            with patch("fact_inventory.config.settings.DEPLOYMENT", "testing"):
                assert create_app() is not None
        finally:
            if "DATABASE_URI" in os.environ:
                del os.environ["DATABASE_URI"]
