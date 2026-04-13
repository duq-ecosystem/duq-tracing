"""
Tests for tracing middleware.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from duq_tracing.context import clear_trace_context, set_trace_id, set_span_id, get_trace_id
from duq_tracing.middleware import (
    TracingMiddleware,
    extract_trace_headers,
    inject_trace_headers,
    TRACE_ID_HEADER,
    SPAN_ID_HEADER,
)
from duq_tracing.models import ServiceName


class MockRequest:
    """Mock Starlette Request for testing."""

    def __init__(
        self,
        path: str = "/api/test",
        method: str = "GET",
        headers: dict = None,
        query_params: dict = None,
    ):
        self.url = MagicMock()
        self.url.path = path
        self.method = method
        self.headers = headers or {}
        self.query_params = query_params
        self.client = MagicMock()
        self.client.host = "127.0.0.1"


class MockResponse:
    """Mock Starlette Response for testing."""

    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.headers = {}


class TestTracingMiddleware:
    """Tests for TracingMiddleware class."""

    def test_init_defaults(self):
        """Should initialize with defaults."""
        mock_publisher = MagicMock()
        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=mock_publisher,
        )

        assert middleware.publisher == mock_publisher
        assert middleware.service == ServiceName.BACKEND
        assert "/health" in middleware.skip_paths

    def test_init_custom_skip_paths(self):
        """Should accept custom skip paths."""
        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=MagicMock(),
            skip_paths=["/custom", "/paths"],
        )

        assert middleware.skip_paths == ["/custom", "/paths"]

    @pytest.mark.asyncio
    async def test_dispatch_skips_health_endpoint(self):
        """Should skip tracing for health endpoints."""
        mock_publisher = AsyncMock()
        app = MagicMock()

        middleware = TracingMiddleware(app=app, publisher=mock_publisher)

        request = MockRequest(path="/health")
        expected_response = MockResponse()
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        # Should call next without publishing
        call_next.assert_called_once_with(request)
        mock_publisher.publish.assert_not_called()
        assert response == expected_response

    @pytest.mark.asyncio
    async def test_dispatch_publishes_events(self):
        """Should publish start and end events for requests."""
        clear_trace_context()

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(return_value=True)

        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=mock_publisher,
        )

        request = MockRequest(path="/api/users", method="POST")
        response = MockResponse(status_code=201)
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        # Should publish twice (start + end)
        assert mock_publisher.publish.call_count == 2

        # Response should have trace headers
        assert TRACE_ID_HEADER in result.headers
        assert SPAN_ID_HEADER in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_uses_incoming_trace_id(self):
        """Should use trace_id from incoming header if present."""
        clear_trace_context()

        mock_publisher = AsyncMock()
        published_events = []

        async def capture_publish(event):
            published_events.append(event)
            return True

        mock_publisher.publish = capture_publish

        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=mock_publisher,
        )

        incoming_trace_id = "incoming-trace-12345"
        request = MockRequest(
            path="/api/test",
            headers={TRACE_ID_HEADER: incoming_trace_id},
        )
        call_next = AsyncMock(return_value=MockResponse())

        response = await middleware.dispatch(request, call_next)

        # Should use incoming trace ID
        assert published_events[0].trace_id == incoming_trace_id
        assert response.headers[TRACE_ID_HEADER] == incoming_trace_id

    @pytest.mark.asyncio
    async def test_dispatch_generates_trace_id_if_missing(self):
        """Should generate new trace_id if not in headers."""
        clear_trace_context()

        mock_publisher = AsyncMock()
        published_events = []

        async def capture_publish(event):
            published_events.append(event)
            return True

        mock_publisher.publish = capture_publish

        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=mock_publisher,
        )

        request = MockRequest(path="/api/test")
        call_next = AsyncMock(return_value=MockResponse())

        response = await middleware.dispatch(request, call_next)

        # Should have generated a trace ID
        assert published_events[0].trace_id is not None
        assert len(published_events[0].trace_id) > 0

    def test_normalize_path_basic(self):
        """Should return path as-is for simple paths."""
        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=MagicMock(),
        )

        assert middleware._normalize_path("/api/users") == "/api/users"
        assert middleware._normalize_path("/health") == "/health"

    def test_normalize_path_replaces_uuids(self):
        """Should replace UUIDs with {id}."""
        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=MagicMock(),
        )

        result = middleware._normalize_path("/api/users/123e4567-e89b-12d3-a456-426614174000")
        assert result == "/api/users/{id}"

    def test_normalize_path_replaces_numeric_ids(self):
        """Should replace long numeric IDs with {id}."""
        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=MagicMock(),
        )

        result = middleware._normalize_path("/api/tasks/12345678901")
        assert result == "/api/tasks/{id}"

    def test_normalize_path_empty(self):
        """Should handle empty/root path."""
        middleware = TracingMiddleware(
            app=MagicMock(),
            publisher=MagicMock(),
        )

        assert middleware._normalize_path("/") == "/"
        assert middleware._normalize_path("") == "/"


class TestExtractTraceHeaders:
    """Tests for extract_trace_headers function."""

    def test_extract_existing_headers(self):
        """Should extract headers when present."""
        request = MockRequest(
            headers={
                TRACE_ID_HEADER: "trace-123",
                SPAN_ID_HEADER: "span-456",
            }
        )

        trace_id, span_id = extract_trace_headers(request)

        assert trace_id == "trace-123"
        assert span_id == "span-456"

    def test_extract_missing_headers(self):
        """Should return None for missing headers."""
        request = MockRequest(headers={})

        trace_id, span_id = extract_trace_headers(request)

        assert trace_id is None
        assert span_id is None

    def test_extract_partial_headers(self):
        """Should handle partial headers."""
        request = MockRequest(
            headers={TRACE_ID_HEADER: "trace-only"}
        )

        trace_id, span_id = extract_trace_headers(request)

        assert trace_id == "trace-only"
        assert span_id is None


class TestInjectTraceHeaders:
    """Tests for inject_trace_headers function."""

    def test_inject_when_context_set(self):
        """Should inject headers when context is set."""
        clear_trace_context()
        set_trace_id("my-trace")
        set_span_id("my-span")

        headers = {}
        result = inject_trace_headers(headers)

        assert result[TRACE_ID_HEADER] == "my-trace"
        assert result[SPAN_ID_HEADER] == "my-span"

    def test_inject_when_context_empty(self):
        """Should not inject headers when context is empty."""
        clear_trace_context()

        headers = {}
        result = inject_trace_headers(headers)

        assert TRACE_ID_HEADER not in result
        assert SPAN_ID_HEADER not in result

    def test_inject_preserves_existing_headers(self):
        """Should preserve existing headers."""
        clear_trace_context()
        set_trace_id("trace")

        headers = {"Content-Type": "application/json"}
        result = inject_trace_headers(headers)

        assert result["Content-Type"] == "application/json"
        assert result[TRACE_ID_HEADER] == "trace"

    def test_inject_partial_context(self):
        """Should only inject available context."""
        clear_trace_context()
        set_trace_id("trace-only")

        headers = {}
        result = inject_trace_headers(headers)

        assert result[TRACE_ID_HEADER] == "trace-only"
        assert SPAN_ID_HEADER not in result
