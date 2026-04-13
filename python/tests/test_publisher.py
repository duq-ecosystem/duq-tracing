"""
Tests for trace publisher.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jarvis_tracing.context import clear_trace_context, set_trace_id, set_span_id
from jarvis_tracing.publisher import (
    TracePublisher,
    TracedOperation,
    get_publisher,
    set_publisher,
)
from jarvis_tracing.models import ServiceName, TraceEvent, TraceStatus


class TestTracePublisher:
    """Tests for TracePublisher class."""

    def test_init_defaults(self):
        """Should initialize with defaults."""
        publisher = TracePublisher()

        assert publisher.redis_url == "redis://localhost:6379"
        assert publisher.channel == "jarvis:traces"
        assert publisher.enabled is True
        assert publisher._redis is None

    def test_init_custom(self):
        """Should accept custom configuration."""
        publisher = TracePublisher(
            redis_url="redis://custom:6380",
            channel="custom:channel",
            enabled=False,
        )

        assert publisher.redis_url == "redis://custom:6380"
        assert publisher.channel == "custom:channel"
        assert publisher.enabled is False

    @pytest.mark.asyncio
    async def test_connect_when_disabled(self):
        """Should not connect when disabled."""
        publisher = TracePublisher(enabled=False)

        await publisher.connect()

        assert publisher._redis is None

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Should connect to Redis successfully."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            publisher = TracePublisher()
            await publisher.connect()

            assert publisher._redis == mock_redis
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Should handle connection failure gracefully."""
        with patch("redis.asyncio.from_url", side_effect=ConnectionError("Failed")):
            publisher = TracePublisher()
            await publisher.connect()

            assert publisher._redis is None

    @pytest.mark.asyncio
    async def test_close(self):
        """Should close Redis connection."""
        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()

        publisher = TracePublisher()
        publisher._redis = mock_redis

        await publisher.close()

        mock_redis.close.assert_called_once()
        assert publisher._redis is None

    @pytest.mark.asyncio
    async def test_publish_when_disabled(self):
        """Should return False when disabled."""
        publisher = TracePublisher(enabled=False)

        event = TraceEvent(
            trace_id="trace",
            span_id="span",
            service=ServiceName.BACKEND,
            operation="test",
            status=TraceStatus.SUCCESS,
        )

        result = await publisher.publish(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_when_not_connected(self):
        """Should return False when not connected."""
        publisher = TracePublisher()
        # _redis is None

        event = TraceEvent(
            trace_id="trace",
            span_id="span",
            service=ServiceName.BACKEND,
            operation="test",
            status=TraceStatus.SUCCESS,
        )

        result = await publisher.publish(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_success(self):
        """Should publish event to Redis channel."""
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        publisher = TracePublisher(channel="test:channel")
        publisher._redis = mock_redis

        event = TraceEvent(
            trace_id="trace-123",
            span_id="span-456",
            service=ServiceName.BACKEND,
            operation="test_op",
            status=TraceStatus.SUCCESS,
        )

        result = await publisher.publish(event)

        assert result is True
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "test:channel"
        assert "trace-123" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_publish_failure(self):
        """Should handle publish failure gracefully."""
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(side_effect=Exception("Publish failed"))

        publisher = TracePublisher()
        publisher._redis = mock_redis

        event = TraceEvent(
            trace_id="trace",
            span_id="span",
            service=ServiceName.BACKEND,
            operation="test",
            status=TraceStatus.SUCCESS,
        )

        result = await publisher.publish(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_start_no_trace_context(self):
        """Should return None when no trace context."""
        clear_trace_context()

        publisher = TracePublisher()
        publisher._redis = AsyncMock()

        result = await publisher.publish_start("operation", ServiceName.BACKEND)

        assert result is None

    @pytest.mark.asyncio
    async def test_publish_start_with_context(self):
        """Should publish start event and return span_id."""
        clear_trace_context()
        set_trace_id("test-trace")
        set_span_id("test-span")

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        publisher = TracePublisher()
        publisher._redis = mock_redis

        result = await publisher.publish_start(
            "my_operation",
            ServiceName.BACKEND,
            metadata={"key": "value"},
        )

        assert result is not None
        # Returns existing span_id from context or generates new one
        assert result == "test-span" or len(result) == 16
        mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_end_no_trace_context(self):
        """Should return False when no trace context."""
        clear_trace_context()

        publisher = TracePublisher()
        publisher._redis = AsyncMock()

        result = await publisher.publish_end(
            "operation",
            ServiceName.BACKEND,
            "span-id",
            TraceStatus.SUCCESS,
            100,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_end_success(self):
        """Should publish end event."""
        clear_trace_context()
        set_trace_id("test-trace")

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        publisher = TracePublisher()
        publisher._redis = mock_redis

        result = await publisher.publish_end(
            "operation",
            ServiceName.BACKEND,
            "span-123",
            TraceStatus.SUCCESS,
            150,
            metadata={"tokens": 100},
            error=None,
        )

        assert result is True


class TestTracedOperation:
    """Tests for TracedOperation context manager."""

    @pytest.mark.asyncio
    async def test_traced_operation_basic(self):
        """Should create span and publish events."""
        clear_trace_context()
        set_trace_id("trace")
        set_span_id("parent")

        published_events = []

        async def capture_publish(event):
            published_events.append(event)
            return True

        mock_publisher = MagicMock(spec=TracePublisher)
        mock_publisher.publish_start = AsyncMock(return_value="new-span-id")
        mock_publisher.publish_end = AsyncMock(return_value=True)

        async with TracedOperation(
            mock_publisher,
            "test_operation",
            ServiceName.BACKEND,
        ) as span:
            assert span.span_id is not None

        mock_publisher.publish_start.assert_called_once()
        mock_publisher.publish_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_traced_operation_adds_metadata(self):
        """Should allow adding metadata during execution."""
        clear_trace_context()
        set_trace_id("trace")

        mock_publisher = MagicMock(spec=TracePublisher)
        mock_publisher.publish_start = AsyncMock(return_value="span")
        mock_publisher.publish_end = AsyncMock(return_value=True)

        async with TracedOperation(
            mock_publisher,
            "operation",
            ServiceName.BACKEND,
        ) as span:
            span.add_metadata("tokens", 1500)
            span.add_tag("model", "claude-3")

        # Check metadata was passed to publish_end
        call_args = mock_publisher.publish_end.call_args
        assert call_args[1]["metadata"]["tokens"] == 1500
        assert call_args[1]["tags"]["model"] == "claude-3"

    @pytest.mark.asyncio
    async def test_traced_operation_error(self):
        """Should mark as error on exception."""
        clear_trace_context()
        set_trace_id("trace")

        mock_publisher = MagicMock(spec=TracePublisher)
        mock_publisher.publish_start = AsyncMock(return_value="span")
        mock_publisher.publish_end = AsyncMock(return_value=True)

        with pytest.raises(ValueError):
            async with TracedOperation(
                mock_publisher,
                "failing_op",
                ServiceName.BACKEND,
            ):
                raise ValueError("Test error")

        # Should publish with ERROR status
        call_args = mock_publisher.publish_end.call_args
        assert call_args[0][3] == TraceStatus.ERROR  # status argument
        assert "Test error" in call_args[1]["error"]

    @pytest.mark.asyncio
    async def test_traced_operation_manual_error(self):
        """Should allow manual error setting."""
        clear_trace_context()
        set_trace_id("trace")

        mock_publisher = MagicMock(spec=TracePublisher)
        mock_publisher.publish_start = AsyncMock(return_value="span")
        mock_publisher.publish_end = AsyncMock(return_value=True)

        async with TracedOperation(
            mock_publisher,
            "operation",
            ServiceName.BACKEND,
        ) as span:
            span.set_error("Manual error message")

        call_args = mock_publisher.publish_end.call_args
        assert call_args[0][3] == TraceStatus.ERROR
        assert call_args[1]["error"] == "Manual error message"


class TestGlobalPublisher:
    """Tests for global publisher functions."""

    def test_get_publisher_initial(self):
        """Should return None initially."""
        # Reset global state
        import jarvis_tracing.publisher as pub_module

        pub_module._publisher = None

        assert get_publisher() is None

    def test_set_and_get_publisher(self):
        """Should set and retrieve publisher."""
        mock_publisher = MagicMock(spec=TracePublisher)

        set_publisher(mock_publisher)

        assert get_publisher() == mock_publisher

        # Clean up
        set_publisher(None)
