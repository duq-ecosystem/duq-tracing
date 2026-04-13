"""
OpenTelemetry Tracing Middleware
================================

FastAPI/Starlette middleware using OpenTelemetry for request tracing.
Uses W3C Trace Context headers (traceparent) with fallback to legacy headers.
"""

import time
from typing import Callable, Optional, Sequence

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.propagate import extract, inject
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from ..models import ServiceName

# Header names (legacy + W3C standard)
TRACE_ID_HEADER = "X-Trace-ID"  # Legacy
SPAN_ID_HEADER = "X-Span-ID"    # Legacy
TRACEPARENT_HEADER = "traceparent"  # W3C standard

# Propagator for W3C Trace Context
propagator = TraceContextTextMapPropagator()


class TracingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for distributed tracing using OpenTelemetry.

    Features:
    - W3C Trace Context propagation (traceparent header)
    - Legacy header support (X-Trace-ID, X-Span-ID)
    - Automatic span creation for requests
    - Error tracking

    Example:
        from jarvis_tracing.otel import TracingMiddleware

        app.add_middleware(
            TracingMiddleware,
            service=ServiceName.BACKEND,
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        service: ServiceName = ServiceName.BACKEND,
        skip_paths: Optional[Sequence[str]] = None,
        **kwargs  # Accept old parameters for compatibility
    ):
        super().__init__(app)
        self.service = service
        self.skip_paths = skip_paths or ["/health", "/metrics", "/favicon.ico"]
        self._tracer = trace.get_tracer(f"jarvis.{service.value}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip tracing for health checks, etc.
        if any(request.url.path.startswith(p) for p in self.skip_paths):
            return await call_next(request)

        # Extract trace context from incoming headers
        # First try W3C traceparent, then fall back to legacy headers
        carrier = dict(request.headers)
        ctx = extract(carrier)

        # Start span with extracted context
        with self._tracer.start_as_current_span(
            f"{request.method} {self._normalize_path(request.url.path)}",
            context=ctx,
            kind=SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.route": request.url.path,
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname,
                "service": self.service.value,
            },
        ) as span:
            start_time = time.perf_counter()

            try:
                response = await call_next(request)

                # Record response info
                span.set_attribute("http.status_code", response.status_code)

                if response.status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                elif response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"Client error {response.status_code}"))

                # Inject trace context into response headers
                response_headers = {}
                inject(response_headers)

                # Add W3C header
                if "traceparent" in response_headers:
                    response.headers["traceparent"] = response_headers["traceparent"]

                # Add legacy headers for compatibility
                span_ctx = span.get_span_context()
                response.headers[TRACE_ID_HEADER] = format(span_ctx.trace_id, "032x")
                response.headers[SPAN_ID_HEADER] = format(span_ctx.span_id, "016x")

                return response

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

            finally:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                span.set_attribute("http.duration_ms", duration_ms)

    def _normalize_path(self, path: str) -> str:
        """Normalize path for consistent span names."""
        parts = path.split("/")
        normalized = []

        for part in parts:
            if not part:
                continue
            # Replace UUIDs and numeric IDs with placeholder
            if len(part) > 8 and ("-" in part or part.isdigit()):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/" + "/".join(normalized) if normalized else "/"


def extract_trace_headers(request: Request) -> tuple[Optional[str], Optional[str]]:
    """
    Extract trace headers from request.

    Returns (trace_id, span_id) tuple from current span context.
    """
    span = trace.get_current_span()
    if span is None:
        return None, None

    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None, None

    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


def inject_trace_headers(headers: dict) -> dict:
    """
    Inject current trace context into headers dict.

    Adds both W3C traceparent and legacy X-Trace-ID headers.
    Use when making outbound HTTP requests.
    """
    # W3C propagation
    inject(headers)

    # Legacy headers
    span = trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            headers[TRACE_ID_HEADER] = format(ctx.trace_id, "032x")
            headers[SPAN_ID_HEADER] = format(ctx.span_id, "016x")

    return headers
