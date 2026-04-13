"""
OpenTelemetry-based Publisher
=============================

Drop-in replacement for TracePublisher using OpenTelemetry SDK.
Provides the same API for backward compatibility.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from ..models import ServiceName, TraceStatus

logger = logging.getLogger(__name__)


class TracePublisher:
    """
    OpenTelemetry-based trace publisher.

    Provides the same API as the original TracePublisher but uses
    OpenTelemetry SDK internally. Spans are exported via configured
    exporters (Redis, OTLP, Console).

    Example:
        from duq_tracing.otel import TracePublisher, configure_tracing, TracingConfig

        # Configure once at startup
        configure_tracing(TracingConfig(redis_enabled=True))

        # Create publisher (now just a thin wrapper)
        publisher = TracePublisher()

        # Use same API
        async with publisher.span("llm_call", ServiceName.BACKEND) as span:
            result = await call_llm()
            span.set_attribute("tokens", result.tokens)
    """

    def __init__(
        self,
        service_name: str = "duq",
        **kwargs  # Accept old parameters for compatibility
    ):
        self.service_name = service_name
        self._tracer = trace.get_tracer(service_name)
        # Ignore old parameters like redis_url, channel - handled by configure_tracing

    async def connect(self) -> None:
        """No-op for compatibility. Connection handled by configure_tracing."""
        pass

    async def close(self) -> None:
        """No-op for compatibility. Cleanup handled by TracerProvider."""
        pass

    @asynccontextmanager
    async def span(
        self,
        operation: str,
        service: ServiceName = ServiceName.BACKEND,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[dict[str, str]] = None,
    ):
        """
        Create a traced span context manager.

        Args:
            operation: Operation name (becomes span name)
            service: Service identifier
            metadata: Additional attributes
            tags: String tags

        Yields:
            OTel Span object with set_attribute method

        Example:
            async with publisher.span("llm_call", ServiceName.BACKEND) as span:
                span.set_attribute("model", "claude-sonnet")
                result = await call_llm()
                span.set_attribute("tokens", result.tokens)
        """
        attributes = {"service": service.value if isinstance(service, ServiceName) else service}

        if metadata:
            attributes.update(metadata)
        if tags:
            attributes.update(tags)

        with self._tracer.start_as_current_span(
            operation,
            attributes=attributes,
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def start_span(
        self,
        operation: str,
        service: ServiceName = ServiceName.BACKEND,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Span:
        """
        Start a span manually (must be ended with span.end()).

        For most cases, use the `span()` context manager instead.
        """
        attributes = {"service": service.value if isinstance(service, ServiceName) else service}
        if metadata:
            attributes.update(metadata)

        return self._tracer.start_span(operation, attributes=attributes)


# Global publisher instance
_publisher: Optional[TracePublisher] = None


def get_publisher() -> Optional[TracePublisher]:
    """Get the global trace publisher."""
    return _publisher


def set_publisher(publisher: TracePublisher) -> None:
    """Set the global trace publisher."""
    global _publisher
    _publisher = publisher
