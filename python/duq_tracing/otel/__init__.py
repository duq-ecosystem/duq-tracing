"""
OpenTelemetry-based Tracing
===========================

Drop-in replacement for duq_tracing using OpenTelemetry SDK.
Provides the same API but with industry-standard tracing.

Migration:
    # Before:
    from duq_tracing import TracePublisher, traced, TracingMiddleware

    # After:
    from duq_tracing.otel import TracePublisher, traced, TracingMiddleware
"""

from .config import configure_tracing, TracingConfig
from .publisher import TracePublisher, get_publisher, set_publisher
from .middleware import TracingMiddleware, TRACE_ID_HEADER, SPAN_ID_HEADER
from .decorators import traced
from .exporter import RedisSpanExporter

# Re-export models for compatibility
from ..models import TraceEvent, ServiceName, TraceStatus, Operations, AlertEvent, AlertSeverity

__all__ = [
    # Config
    "configure_tracing",
    "TracingConfig",
    # Publisher
    "TracePublisher",
    "get_publisher",
    "set_publisher",
    # Middleware
    "TracingMiddleware",
    "TRACE_ID_HEADER",
    "SPAN_ID_HEADER",
    # Decorators
    "traced",
    # Exporter
    "RedisSpanExporter",
    # Models (re-exported)
    "TraceEvent",
    "ServiceName",
    "TraceStatus",
    "Operations",
    "AlertEvent",
    "AlertSeverity",
]
