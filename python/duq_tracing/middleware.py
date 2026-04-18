"""
Tracing Middleware
==================

FastAPI/Starlette middleware for automatic request tracing.
Extracts or generates trace_id from X-Trace-ID header.
"""

import re
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

# Security: UUID v4 pattern for trace ID validation
UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Security: Sensitive query parameter keys to mask
SENSITIVE_QUERY_KEYS = frozenset({
    "api_key", "apikey", "token", "access_token", "refresh_token",
    "password", "secret", "credential", "auth", "key", "bearer",
})


def _is_valid_trace_id(trace_id: str) -> bool:
    """Validate trace ID format (UUID v4)."""
    return bool(UUID_V4_PATTERN.match(trace_id))


def _sanitize_query_params(params: str) -> str:
    """Sanitize query parameters, masking sensitive values."""
    if not params:
        return None

    sanitized_parts = []
    for part in params.split("&"):
        if "=" in part:
            key, _, value = part.partition("=")
            if key.lower() in SENSITIVE_QUERY_KEYS:
                sanitized_parts.append(f"{key}=***")
            else:
                sanitized_parts.append(part)
        else:
            sanitized_parts.append(part)

    return "&".join(sanitized_parts) if sanitized_parts else None


def _sanitize_error_message(error_msg: str) -> str:
    """Sanitize error message, removing potential sensitive data."""
    if not error_msg:
        return None

    # Truncate long messages
    if len(error_msg) > 200:
        error_msg = error_msg[:200] + "..."

    # Mask common sensitive patterns
    error_msg = re.sub(r"password['\"]?\s*[=:]\s*['\"]?[^'\"\s,\)]+", "password=***", error_msg, flags=re.IGNORECASE)
    error_msg = re.sub(r"api[_-]?key['\"]?\s*[=:]\s*['\"]?[^'\"\s,\)]+", "api_key=***", error_msg, flags=re.IGNORECASE)
    error_msg = re.sub(r"token['\"]?\s*[=:]\s*['\"]?[^'\"\s,\)]+", "token=***", error_msg, flags=re.IGNORECASE)
    error_msg = re.sub(r"@[a-z0-9\-\.]+:[^@]+@", "@***:***@", error_msg, flags=re.IGNORECASE)

    return error_msg


class TracingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for distributed tracing.

    Features:
    - Extracts trace_id from X-Trace-ID header or generates new one
    - Sets trace context for the request lifecycle
    - Publishes start/end events for API requests
    - Adds X-Trace-ID to response headers

    Example:
        from duq_tracing import TracingMiddleware, TracePublisher

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

        # Security: Extract and validate trace_id from header
        header_trace_id = request.headers.get(TRACE_ID_HEADER)
        if header_trace_id and _is_valid_trace_id(header_trace_id):
            trace_id = header_trace_id
        else:
            trace_id = generate_trace_id()
        span_id = generate_span_id()

        # Set context for this request
        with TraceContext(trace_id) as ctx:
            start_time = time.perf_counter()

            # Build metadata (Security: sanitize query params)
            raw_query = str(request.query_params) if request.query_params else None
            metadata = {
                "method": request.method,
                "path": request.url.path,
                "query": _sanitize_query_params(raw_query),
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
                # Security: Sanitize error message before including in trace
                raw_error = f"{type(e).__name__}: {str(e)}"
                error_msg = _sanitize_error_message(raw_error)
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
