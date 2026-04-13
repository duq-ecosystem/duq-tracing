"""
Duq Tracing Library
===================

Distributed tracing for Duq services.

Quick Start:
    from duq_tracing import (
        TracePublisher,
        TracingMiddleware,
        traced,
        ServiceName,
    )

    # Initialize publisher
    publisher = TracePublisher(redis_url="redis://localhost:6379")
    await publisher.connect()

    # Add middleware to FastAPI
    app.add_middleware(
        TracingMiddleware,
        publisher=publisher,
        service=ServiceName.BACKEND,
    )

    # Decorate functions
    @traced("llm_call")
    async def call_llm():
        ...
"""

from .context import (
    SpanContext,
    TraceContext,
    clear_trace_context,
    generate_span_id,
    generate_trace_id,
    get_or_create_trace_id,
    get_parent_span_id,
    get_span_id,
    get_trace_id,
    get_trace_context,
    set_parent_span_id,
    set_span_id,
    set_trace_id,
)
from .decorators import traced, TracedClass
from .middleware import (
    TracingMiddleware,
    TRACE_ID_HEADER,
    SPAN_ID_HEADER,
    extract_trace_headers,
    inject_trace_headers,
)
from .models import Operations, ServiceName, TraceEvent, TraceStatus
from .publisher import (
    TracePublisher,
    TracedOperation,
    get_publisher,
    set_publisher,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "TraceEvent",
    "TraceStatus",
    "ServiceName",
    "Operations",
    # Context
    "TraceContext",
    "SpanContext",
    "get_trace_id",
    "get_span_id",
    "get_parent_span_id",
    "set_trace_id",
    "set_span_id",
    "set_parent_span_id",
    "get_or_create_trace_id",
    "get_trace_context",
    "clear_trace_context",
    "generate_trace_id",
    "generate_span_id",
    # Publisher
    "TracePublisher",
    "TracedOperation",
    "get_publisher",
    "set_publisher",
    # Middleware
    "TracingMiddleware",
    "TRACE_ID_HEADER",
    "SPAN_ID_HEADER",
    "extract_trace_headers",
    "inject_trace_headers",
    # Decorators
    "traced",
    "TracedClass",
]
