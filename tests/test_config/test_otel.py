"""Tests for OpenTelemetry trace context management."""

from unittest.mock import MagicMock, patch

from fact_inventory.config.otel import get_span_id, get_trace_id


class TestGetTraceId:
    """Test get_trace_id function."""

    def test_returns_valid_trace_id_when_span_exists(self) -> None:
        """Test that get_trace_id returns a valid hex trace_id."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 12345678901234567890123456789012
        mock_ctx.span_id = 9876543210987654
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            trace_id = get_trace_id()

        assert isinstance(trace_id, str)
        assert len(trace_id) == 32
        assert trace_id == format(mock_ctx.trace_id, "032x")

    def test_returns_zero_when_no_trace_id(self) -> None:
        """Test that get_trace_id returns '0' * 32 when trace_id is None."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = None
        mock_ctx.span_id = 9876543210987654
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            trace_id = get_trace_id()

        assert trace_id == "0" * 32

    def test_returns_zero_when_no_span_context(self) -> None:
        """Test that get_trace_id returns '0' * 32 when span has no context."""
        mock_span = MagicMock()
        mock_span.get_span_context.return_value = None

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            trace_id = get_trace_id()

        assert trace_id == "0" * 32

    def test_returns_zero_when_span_is_invalid(self) -> None:
        """Test that get_trace_id handles invalid span gracefully."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0
        mock_ctx.span_id = 0
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            trace_id = get_trace_id()

        assert trace_id == "0" * 32

    def test_trace_id_format_is_lowercase_hex(self) -> None:
        """Test that trace_id is formatted as lowercase hex string."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        # Use a trace_id that would be different in uppercase
        mock_ctx.trace_id = 0xDEADBEEF00000000123456789ABCDEF0
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            trace_id = get_trace_id()

        assert trace_id == trace_id.lower()
        assert all(c in "0123456789abcdef" for c in trace_id)


class TestGetSpanId:
    """Test get_span_id function."""

    def test_returns_valid_span_id_when_span_exists(self) -> None:
        """Test that get_span_id returns a valid hex span_id."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 12345678901234567890123456789012
        mock_ctx.span_id = 9876543210987654
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            span_id = get_span_id()

        assert isinstance(span_id, str)
        assert len(span_id) == 16
        assert span_id == format(mock_ctx.span_id, "016x")

    def test_returns_zero_when_no_span_id(self) -> None:
        """Test that get_span_id returns '0' * 16 when span_id is None."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 12345678901234567890123456789012
        mock_ctx.span_id = None
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            span_id = get_span_id()

        assert span_id == "0" * 16

    def test_returns_zero_when_no_span_context(self) -> None:
        """Test that get_span_id returns '0' * 16 when span has no context."""
        mock_span = MagicMock()
        mock_span.get_span_context.return_value = None

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            span_id = get_span_id()

        assert span_id == "0" * 16

    def test_returns_zero_when_span_is_invalid(self) -> None:
        """Test that get_span_id handles invalid span gracefully."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0
        mock_ctx.span_id = 0
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            span_id = get_span_id()

        assert span_id == "0" * 16

    def test_span_id_format_is_lowercase_hex(self) -> None:
        """Test that span_id is formatted as lowercase hex string."""
        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.span_id = 0xDEADBEEF00000000
        mock_span.get_span_context.return_value = mock_ctx

        with patch(
            "fact_inventory.config.otel.get_current_span", return_value=mock_span
        ):
            span_id = get_span_id()

        assert span_id == span_id.lower()
        assert all(c in "0123456789abcdef" for c in span_id)
