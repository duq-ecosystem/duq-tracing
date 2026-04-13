"""
Tracing Middleware
==================

FastAPI/Starlette middleware for automatic request tracing.
Extracts or generates trace_id from X-Trace-ID header.
"""

import time
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .context import (
    TraceContext,
    generate_span_id,
    generate_trace_id,
    get_span_id,
    get_trace_id,
    set_span_id,
    set_trace_id,
)
from .models import Operations, ServiceName, TraceEvent, TraceStatus
from .publisher import TracePublisher


# Header names
TRACE_ID_HEADER = "X-Trace-ID"
SPAN_ID_HEADER = "X-Span-ID"


class TracingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for distributed tracing.

    Features:
    - Extracts trace_id from X-Trace-ID header or generates new one
    - Sets trace context for the request lifecycle
    - Publishes start/end events for API requests
    - Adds X-Trace-ID to response headers

    Example:
        from jarvis_tracing import TracingMiddleware, TracePublisher

        publisher = TracePublisher(redis_url="redis://localhost:6379")
        await publisher.connect()

        app.add_middleware(
            TracingMiddleware,
            publisher=publisher,
            service=ServiceName.BACKEND,
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        publisher: TracePublisher,
        service: ServiceName = ServiceName.BACKEND,
        skip_paths: Optional[list[str]] = None,
    ):
        super().__init__(app)
        self.publisher = publisher
        self.service = service
        self.skip_paths = skip_paths or ["/health", "/metrics", "/favicon.ico"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip tracing for certain paths
        if any(request.url.path.startswith(p) for p in self.skip_paths):
            return await call_next(request)

        # Extract or generate trace_id
        trace_id = request.headers.get(TRACE_ID_HEADER) or generate_trace_id()
        span_id = generate_span_id()

        # Set context for this request
        with TraceContext(trace_id) as ctx:
            start_time = time.perf_counter()

            # Build metadata
            metadata = {
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params) if request.query_params else None,
                "client_host": request.client.host if request.client else None,
            }

            # Publish start event
            start_event = TraceEvent(
                trace_id=trace_id,
                span_id=ctx.span_id,
                service=self.service,
                operation=Operations.API_REQUEST,
                status=TraceStatus.STARTED,
                metadata=metadata,
                tags={
                    "endpoint": self._normalize_path(request.url.path),
                    "method": request.method,
                },
            )
            await self.publisher.publish(start_event)

            # Process request
            status_code = 500
            error_msg = None

            try:
                response = await call_next(request)
                status_code = response.status_code

                # Add trace headers to response
                response.headers[TRACE_ID_HEADER] = trace_id
                response.headers[SPAN_ID_HEADER] = ctx.span_id

                return response

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                raise

            finally:
                # Calculate duration
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                # Update metadata
                metadata["status_code"] = status_code
                metadata["duration_ms"] = duration_ms

                # Determine status
                if error_msg or status_code >= 500:
                    status = TraceStatus.ERROR
                else:
                    status = TraceStatus.SUCCESS

                # Publish end event
                end_event = TraceEvent(
                    trace_id=trace_id,
                    span_id=ctx.span_id,
                    service=self.service,
                    operation=Operations.API_REQUEST,
                    status=status,
                    duration_ms=duration_ms,
                    metadata=metadata,
                    tags={
                        "endpoint": self._normalize_path(request.url.path),
                        "method": request.method,
                        "status_code": str(status_code),
                    },
                    error=error_msg,
                )
                await self.publisher.publish(end_event)

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path for consistent tagging.

        /api/users/123 -> /api/users/{id}
        /api/tasks/abc-def -> /api/tasks/{id}
        """
        parts = path.split("/")
        normalized = []

        for part in parts:
            if not part:
                continue
            # UUID-like or numeric ID
            if len(part) > 8 and ("-" in part or part.isdigit()):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/" + "/".join(normalized) if normalized else "/"


def extract_trace_headers(request: Request) -> tuple[Optional[str], Optional[str]]:
    """
    Extract trace headers from request.

    Returns (trace_id, span_id) tuple.
    """
    return (
        request.headers.get(TRACE_ID_HEADER),
        request.headers.get(SPAN_ID_HEADER),
    )


def inject_trace_headers(headers: dict) -> dict:
    """
    Inject current trace context into headers dict.

    Use when making outbound HTTP requests.
    """
    trace_id = get_trace_id()
    span_id = get_span_id()

    if trace_id:
        headers[TRACE_ID_HEADER] = trace_id
    if span_id:
        headers[SPAN_ID_HEADER] = span_id

    return headers
