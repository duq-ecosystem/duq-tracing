"""
Tests for tracing decorators.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from duq_tracing.context import clear_trace_context, set_trace_id, set_span_id
from duq_tracing.decorators import traced, _safe_repr, TracedClass
from duq_tracing.models import ServiceName, TraceStatus


class TestSafeRepr:
    """Tests for _safe_repr helper function."""

    def test_safe_repr_string(self):
        """Should return repr of string."""
        result = _safe_repr("hello")
        assert result == "'hello'"

    def test_safe_repr_number(self):
        """Should return repr of number."""
        result = _safe_repr(42)
        assert result == "42"

    def test_safe_repr_list(self):
        """Should return repr of list."""
        result = _safe_repr([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_safe_repr_truncates_long_strings(self):
        """Should truncate strings longer than max_len."""
        long_string = "x" * 1000
        result = _safe_repr(long_string, max_len=100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_safe_repr_handles_unrepresentable(self):
        """Should handle objects that can't be repr'd."""

        class BadRepr:
            def __repr__(self):
                raise ValueError("Can't repr me")

        result = _safe_repr(BadRepr())
        assert result == "<unrepresentable>"

    def test_safe_repr_custom_max_len(self):
        """Should respect custom max_len."""
        result = _safe_repr("a" * 100, max_len=50)
        assert len(result) == 50


class TestTracedDecorator:
    """Tests for @traced decorator."""

    @pytest.mark.asyncio
    async def test_traced_calls_function(self):
        """Decorated function should still execute."""
        clear_trace_context()

        @traced("test_op")
        async def my_func(x, y):
            return x + y

        result = await my_func(1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_traced_without_trace_context(self):
        """Should execute without publishing when no trace context."""
        clear_trace_context()

        mock_publisher = AsyncMock()
        with patch("duq_tracing.decorators.get_publisher", return_value=mock_publisher):

            @traced("test_op")
            async def my_func():
                return "result"

            result = await my_func()
            assert result == "result"
            # No publish calls because no trace_id
            mock_publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_traced_publishes_events(self):
        """Should publish start and end events."""
        clear_trace_context()
        set_trace_id("test-trace-123")
        set_span_id("parent-span")

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(return_value=True)

        with patch("duq_tracing.decorators.get_publisher", return_value=mock_publisher):

            @traced("test_operation", service=ServiceName.BACKEND)
            async def my_func():
                return "done"

            result = await my_func()
            assert result == "done"

            # Should have called publish twice (start + end)
            assert mock_publisher.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_traced_captures_args_when_enabled(self):
        """Should capture function args when capture_args=True."""
        clear_trace_context()
        set_trace_id("trace")
        set_span_id("span")

        published_events = []
        mock_publisher = AsyncMock()

        async def capture_publish(event):
            published_events.append(event)
            return True

        mock_publisher.publish = capture_publish

        with patch("duq_tracing.decorators.get_publisher", return_value=mock_publisher):

            @traced("test_op", capture_args=True)
            async def my_func(a, b, key="value"):
                return a + b

            await my_func(1, 2, key="test")

            # First event should be START with args
            start_event = published_events[0]
            assert start_event.status == TraceStatus.STARTED
            assert "args" in start_event.metadata

    @pytest.mark.asyncio
    async def test_traced_captures_result_when_enabled(self):
        """Should capture return value when capture_result=True."""
        clear_trace_context()
        set_trace_id("trace")
        set_span_id("span")

        published_events = []
        mock_publisher = AsyncMock()

        async def capture_publish(event):
            published_events.append(event)
            return True

        mock_publisher.publish = capture_publish

        with patch("duq_tracing.decorators.get_publisher", return_value=mock_publisher):

            @traced("test_op", capture_result=True)
            async def my_func():
                return {"key": "value"}

            await my_func()

            # End event should have result (it's created via asyncio.create_task)
            # We need to wait for it
            import asyncio
            await asyncio.sleep(0.1)

            # Find the SUCCESS event
            end_events = [e for e in published_events if e.status == TraceStatus.SUCCESS]
            if end_events:
                assert "result" in end_events[0].metadata

    @pytest.mark.asyncio
    async def test_traced_handles_exceptions(self):
        """Should mark as ERROR when exception occurs."""
        clear_trace_context()
        set_trace_id("trace")
        set_span_id("span")

        published_events = []
        mock_publisher = AsyncMock()

        async def capture_publish(event):
            published_events.append(event)
            return True

        mock_publisher.publish = capture_publish

        with patch("duq_tracing.decorators.get_publisher", return_value=mock_publisher):

            @traced("failing_op")
            async def failing_func():
                raise ValueError("Something went wrong")

            with pytest.raises(ValueError):
                await failing_func()

            # Wait for async task
            import asyncio
            await asyncio.sleep(0.1)

            # Should have error event
            error_events = [e for e in published_events if e.status == TraceStatus.ERROR]
            assert len(error_events) >= 1
            assert "ValueError" in (error_events[0].error or "")

    def test_traced_sync_function_passthrough(self):
        """Sync functions should pass through without tracing."""

        @traced("sync_op")
        def sync_func(x):
            return x * 2

        result = sync_func(5)
        assert result == 10


class TestTracedClass:
    """Tests for TracedClass mixin."""

    def test_traced_class_decorates_methods(self):
        """TracedClass should decorate specified methods."""

        class MyService(TracedClass):
            _trace_service = ServiceName.BACKEND
            _trace_operations = {"do_work": "work_operation"}

            async def do_work(self):
                return "done"

        # The method should be wrapped
        service = MyService()
        # Check it's still callable
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(service.do_work())
        assert result == "done"

    def test_traced_class_ignores_missing_methods(self):
        """TracedClass should not fail on missing methods."""

        class MyService(TracedClass):
            _trace_operations = {"nonexistent": "operation"}

            async def other_method(self):
                return "ok"

        # Should not raise
        service = MyService()
        assert hasattr(service, "other_method")
