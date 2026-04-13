"""
Tests for tracing models.
"""

import pytest
from datetime import datetime

from jarvis_tracing.models import (
    TraceEvent,
    ServiceName,
    TraceStatus,
    Operations,
)


class TestServiceName:
    """Tests for ServiceName enum."""

    def test_gateway_value(self):
        """Gateway should have correct value."""
        assert ServiceName.GATEWAY.value == "gateway"

    def test_backend_value(self):
        """Backend should have correct value."""
        assert ServiceName.BACKEND.value == "backend"

    def test_admin_value(self):
        """Admin should have correct value."""
        assert ServiceName.ADMIN.value == "admin"

    def test_string_conversion(self):
        """Enum should convert to string value."""
        assert ServiceName.GATEWAY.value == "gateway"
        assert ServiceName.BACKEND.value == "backend"


class TestTraceStatus:
    """Tests for TraceStatus enum."""

    def test_started_value(self):
        """Started should have correct value."""
        assert TraceStatus.STARTED.value == "started"

    def test_success_value(self):
        """Success should have correct value."""
        assert TraceStatus.SUCCESS.value == "success"

    def test_error_value(self):
        """Error should have correct value."""
        assert TraceStatus.ERROR.value == "error"


class TestTraceEvent:
    """Tests for TraceEvent model."""

    def test_create_minimal_event(self):
        """Should create event with required fields only."""
        event = TraceEvent(
            trace_id="550e8400-e29b-41d4-a716-446655440000",
            span_id="7a8b9c0d1e2f3456",
            service=ServiceName.BACKEND,
            operation="test_op",
            status=TraceStatus.SUCCESS,
        )

        assert event.trace_id == "550e8400-e29b-41d4-a716-446655440000"
        assert event.span_id == "7a8b9c0d1e2f3456"
        assert event.service == ServiceName.BACKEND
        assert event.operation == "test_op"
        assert event.status == TraceStatus.SUCCESS

    def test_create_full_event(self):
        """Should create event with all fields."""
        now = datetime.utcnow()
        event = TraceEvent(
            trace_id="trace123",
            span_id="span456",
            parent_span_id="parent789",
            service=ServiceName.GATEWAY,
            operation="http_request",
            timestamp=now,
            status=TraceStatus.SUCCESS,
            duration_ms=100,
            metadata={"key": "value"},
            tags={"env": "test"},
            error=None,
        )

        assert event.parent_span_id == "parent789"
        assert event.duration_ms == 100
        assert event.metadata == {"key": "value"}
        assert event.tags == {"env": "test"}
        assert event.timestamp == now

    def test_default_timestamp(self):
        """Timestamp should default to now."""
        event = TraceEvent(
            trace_id="trace",
            span_id="span",
            service=ServiceName.BACKEND,
            operation="op",
            status=TraceStatus.STARTED,
        )

        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_default_metadata_and_tags(self):
        """Metadata and tags should default to empty dicts."""
        event = TraceEvent(
            trace_id="trace",
            span_id="span",
            service=ServiceName.BACKEND,
            operation="op",
            status=TraceStatus.STARTED,
        )

        assert event.metadata == {}
        assert event.tags == {}

    def test_json_serialization(self):
        """Event should serialize to JSON."""
        event = TraceEvent(
            trace_id="trace123",
            span_id="span456",
            service=ServiceName.BACKEND,
            operation="test",
            status=TraceStatus.SUCCESS,
        )

        json_data = event.model_dump_json()
        assert "trace123" in json_data
        assert "span456" in json_data
        assert "backend" in json_data

    def test_error_event(self):
        """Should create event with error."""
        event = TraceEvent(
            trace_id="trace",
            span_id="span",
            service=ServiceName.BACKEND,
            operation="failed_op",
            status=TraceStatus.ERROR,
            error="Something went wrong",
        )

        assert event.status == TraceStatus.ERROR
        assert event.error == "Something went wrong"


class TestOperations:
    """Tests for Operations constants."""

    def test_http_request_received(self):
        """Should have HTTP request received operation."""
        assert Operations.HTTP_REQUEST_RECEIVED == "http_request_received"

    def test_llm_call(self):
        """Should have LLM call operation."""
        assert Operations.LLM_CALL == "llm_call"

    def test_tool_execution(self):
        """Should have tool execution operation."""
        assert Operations.TOOL_EXECUTION == "tool_execution"

    def test_memory_operations(self):
        """Should have memory operations."""
        assert Operations.MEMORY_SEARCH == "memory_search"
        assert Operations.MEMORY_STORE == "memory_store"

    def test_obsidian_operations(self):
        """Should have Obsidian operations."""
        assert Operations.OBSIDIAN_READ == "obsidian_read"
        assert Operations.OBSIDIAN_WRITE == "obsidian_write"

    def test_queue_operations(self):
        """Should have queue operations."""
        assert Operations.QUEUE_ENQUEUE == "queue_enqueue"
        assert Operations.QUEUE_EXECUTE == "queue_execute"
