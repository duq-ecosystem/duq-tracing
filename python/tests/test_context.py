"""
Tests for trace context management.
"""

import pytest
import asyncio

from jarvis_tracing.context import (
    generate_trace_id,
    generate_span_id,
    get_trace_id,
    set_trace_id,
    get_span_id,
    set_span_id,
    get_or_create_trace_id,
    clear_trace_context,
    get_trace_context,
    get_parent_span_id,
    TraceContext,
    SpanContext,
)


class TestIdGeneration:
    """Tests for ID generation functions."""

    def test_generate_trace_id_is_uuid(self):
        """Trace ID should be valid UUID format."""
        trace_id = generate_trace_id()
        # UUID v4 format: 8-4-4-4-12
        parts = trace_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_generate_trace_id_is_unique(self):
        """Each call should generate unique trace ID."""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_span_id_length(self):
        """Span ID should be 16 hex characters."""
        span_id = generate_span_id()
        assert len(span_id) == 16
        # Should be valid hex
        int(span_id, 16)

    def test_generate_span_id_is_unique(self):
        """Each call should generate unique span ID."""
        ids = [generate_span_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestContextVars:
    """Tests for context variable management."""

    def test_set_and_get_trace_id(self):
        """Should store and retrieve trace ID."""
        clear_trace_context()
        set_trace_id("test-trace-id")
        assert get_trace_id() == "test-trace-id"

    def test_set_and_get_span_id(self):
        """Should store and retrieve span ID."""
        clear_trace_context()
        set_span_id("test-span-id")
        assert get_span_id() == "test-span-id"

    def test_get_trace_id_returns_none_when_not_set(self):
        """Should return None when trace ID not set."""
        clear_trace_context()
        assert get_trace_id() is None

    def test_get_or_create_trace_id_creates_new(self):
        """Should create new trace ID when not set."""
        clear_trace_context()
        trace_id = get_or_create_trace_id()
        assert trace_id is not None
        assert len(trace_id) > 0
        # Verify it was stored
        assert get_trace_id() == trace_id

    def test_get_or_create_trace_id_returns_existing(self):
        """Should return existing trace ID when set."""
        clear_trace_context()
        set_trace_id("existing-trace")
        trace_id = get_or_create_trace_id()
        assert trace_id == "existing-trace"

    def test_clear_trace_context(self):
        """Should clear all context vars."""
        set_trace_id("trace")
        set_span_id("span")
        clear_trace_context()
        assert get_trace_id() is None
        assert get_span_id() is None

    def test_get_trace_context(self):
        """Should return dict with trace context."""
        clear_trace_context()
        set_trace_id("trace-123")
        set_span_id("span-456")

        ctx = get_trace_context()

        assert ctx["trace_id"] == "trace-123"
        assert ctx["span_id"] == "span-456"
        assert ctx["parent_span_id"] is None


class TestTraceContext:
    """Tests for TraceContext context manager."""

    def test_trace_context_sets_ids(self):
        """TraceContext should set trace and span IDs."""
        clear_trace_context()

        with TraceContext("test-trace") as ctx:
            assert get_trace_id() == "test-trace"
            assert get_span_id() == ctx.span_id
            assert ctx.span_id is not None

    def test_trace_context_restores_previous(self):
        """TraceContext should restore previous context on exit."""
        clear_trace_context()
        original_token = set_trace_id("original-trace")
        set_span_id("original-span")

        with TraceContext("new-trace"):
            assert get_trace_id() == "new-trace"

        # After exit, context is restored
        assert get_trace_id() == "original-trace"

    def test_trace_context_generates_trace_id_if_none(self):
        """TraceContext should generate trace_id if not provided."""
        clear_trace_context()

        with TraceContext() as ctx:
            assert ctx.trace_id is not None
            assert len(ctx.trace_id) > 0
            assert get_trace_id() == ctx.trace_id

    def test_trace_context_generates_span_id(self):
        """TraceContext should always generate a span_id."""
        clear_trace_context()

        with TraceContext("trace") as ctx:
            assert ctx.span_id is not None
            assert len(ctx.span_id) == 16


class TestSpanContext:
    """Tests for SpanContext context manager."""

    def test_span_context_sets_new_span(self):
        """SpanContext should set new span ID while preserving trace."""
        clear_trace_context()
        set_trace_id("my-trace")
        original_span = generate_span_id()
        set_span_id(original_span)

        with SpanContext() as new_span_id:
            # Should have new span
            assert get_span_id() == new_span_id
            assert new_span_id != original_span
            # Parent should be original span
            assert get_parent_span_id() == original_span
            # Trace should be preserved
            assert get_trace_id() == "my-trace"

    def test_span_context_restores_span_on_exit(self):
        """SpanContext should restore original span on exit."""
        clear_trace_context()
        set_trace_id("trace")
        set_span_id("original-span")

        with SpanContext():
            pass

        assert get_span_id() == "original-span"

    def test_span_context_returns_span_id(self):
        """SpanContext should return new span_id from __enter__."""
        clear_trace_context()
        set_span_id("original")

        with SpanContext() as span_id:
            assert span_id is not None
            assert len(span_id) == 16
            assert span_id != "original"


@pytest.mark.asyncio
async def test_context_isolation_across_tasks():
    """Context should be isolated across async tasks."""
    clear_trace_context()

    results = {}

    async def task1():
        set_trace_id("trace-1")
        await asyncio.sleep(0.01)
        results["task1"] = get_trace_id()

    async def task2():
        set_trace_id("trace-2")
        await asyncio.sleep(0.01)
        results["task2"] = get_trace_id()

    await asyncio.gather(task1(), task2())

    # Each task should have its own context
    assert results["task1"] == "trace-1"
    assert results["task2"] == "trace-2"
