"""Tests for OTEL-compliant structlog configuration."""

from unittest.mock import patch

import structlog
from fact_inventory.config.logging import (
    _add_otel_trace_context,
    _add_resource,
    _filter_empty_values,
    get_structlog_config,
)


class TestAddTraceContext:
    """Test _add_otel_trace_context processor."""

    def test_adds_trace_id_when_available(self) -> None:
        """Test that trace_id is added when available."""
        event_dict: dict[str, str] = {}

        with patch("fact_inventory.config.logging.get_trace_id", return_value="abc123"):
            result = _add_otel_trace_context(None, None, event_dict)

        assert result["trace_id"] == "abc123"

    def test_adds_trace_id_when_zero(self) -> None:
        """Test that trace_id is '0' * 32 when get_trace_id returns '0' * 32."""
        event_dict: dict[str, str] = {}

        with patch("fact_inventory.config.logging.get_trace_id", return_value="0" * 32):
            result = _add_otel_trace_context(None, None, event_dict)

        assert result["trace_id"] == "0" * 32

    def test_adds_span_id_when_zero(self) -> None:
        """Test that span_id is '0' * 16 when get_span_id returns '0' * 16."""
        event_dict: dict[str, str] = {}

        with patch("fact_inventory.config.logging.get_span_id", return_value="0" * 16):
            result = _add_otel_trace_context(None, None, event_dict)

        assert result["span_id"] == "0" * 16


class TestAddResource:
    """Test _add_resource processor."""

    def test_minimum_required_fields_present(self) -> None:
        """Test that resource dict has minimum required fields."""
        event_dict: dict[str, str] = {}

        with (
            patch("fact_inventory.config.settings") as mock_settings,
            patch("fact_inventory.config.logging.os.getenv", return_value="test-host"),
            patch(
                "fact_inventory.config.logging.socket.gethostname",
                return_value="test-host",
            ),
        ):
            mock_settings.app_name = "test-app"
            mock_settings.version = "1.0.0"
            mock_settings.deployment_environment = "development"
            result = _add_resource(None, None, event_dict)

        resource = result["resource"]
        assert "service.name" in resource
        assert "service.version" in resource
        assert "host.name" in resource
        assert "deployment.environment" in resource

    def test_service_namespace_added_when_not_none(self) -> None:
        """Test that service.namespace is added when environment variable is set."""
        event_dict: dict[str, str] = {}

        with (
            patch("fact_inventory.config.settings") as mock_settings,
            patch(
                "fact_inventory.config.logging.os.getenv",
                side_effect=lambda k, _v=None: (
                    "test-namespace" if k == "SERVICE_NAMESPACE" else "test-host"
                ),
            ),
            patch(
                "fact_inventory.config.logging.socket.gethostname",
                return_value="test-host",
            ),
        ):
            mock_settings.app_name = "test-app"
            mock_settings.version = "1.0.0"
            mock_settings.deployment_environment = "development"
            result = _add_resource(None, None, event_dict)

        resource = result["resource"]
        assert resource["service.namespace"] == "test-namespace"

    def test_service_namespace_omitted_when_none(self) -> None:
        """Test that service.namespace is omitted when environment variable is None."""
        event_dict: dict[str, str] = {}

        def mock_getenv(key: str, _default=None):
            if key == "SERVICE_NAMESPACE":
                return None
            return "test-host"

        with (
            patch("fact_inventory.config.settings") as mock_settings,
            patch("fact_inventory.config.logging.os.getenv", side_effect=mock_getenv),
            patch(
                "fact_inventory.config.logging.socket.gethostname",
                return_value="test-host",
            ),
        ):
            mock_settings.app_name = "test-app"
            mock_settings.version = "1.0.0"
            mock_settings.deployment_environment = "development"
            result = _add_resource(None, None, event_dict)

        resource = result["resource"]
        assert "service.namespace" not in resource


class TestFilterEmptyValues:
    """Test _filter_empty_values processor."""

    def test_removes_none_values(self) -> None:
        """Test that None values are removed."""
        event_dict = {"key1": "value1", "key2": None, "key3": "value3"}

        result = _filter_empty_values(None, None, event_dict)

        assert "key1" in result
        assert "key2" not in result
        assert "key3" in result

    def test_preserves_falsy_values_except_none(self) -> None:
        """Test that empty string, 0, False are preserved."""
        event_dict = {"empty_str": "", "zero": 0, "false": False, "none": None}

        result = _filter_empty_values(None, None, event_dict)

        assert result["empty_str"] == ""
        assert result["zero"] == 0
        assert result["false"] is False
        assert "none" not in result


class TestGetStructlogConfig:
    """Test get_structlog_config function."""

    def test_config_has_expected_processors(self) -> None:
        """Test that the config has the expected processor order."""
        config = get_structlog_config()

        assert config.structlog_logging_config is not None
        processors = config.structlog_logging_config.processors

        assert len(processors) == 6

    def test_config_uses_stdout_logger_factory(self) -> None:
        """Test that the config uses PrintLoggerFactory with stdout."""
        config = get_structlog_config()

        assert config.structlog_logging_config is not None
        assert isinstance(
            config.structlog_logging_config.logger_factory,
            structlog.PrintLoggerFactory,
        )

    def test_config_enables_middleware_logging(self) -> None:
        """Test that middleware logging is enabled."""
        config = get_structlog_config()

        assert config.enable_middleware_logging is True

    def test_config_logs_exceptions_always(self) -> None:
        """Test that log_exceptions is set to 'always'."""
        config = get_structlog_config()

        assert config.structlog_logging_config.log_exceptions == "always"
