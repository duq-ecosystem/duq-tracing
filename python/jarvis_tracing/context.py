"""
Trace Context Management
========================

ContextVar-based trace propagation for async Python code.
Ensures trace_id and span_id are available throughout request lifecycle.
"""

import contextvars
import secrets
from typing import Optional
from uuid import uuid4


# Context variables for trace propagation
_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)
_span_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "span_id", default=None
)
_parent_span_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "parent_span_id", default=None
)


def generate_trace_id() -> str:
    """Generate a new trace ID (UUID v4)."""
    return str(uuid4())


def generate_span_id() -> str:
    """Generate a new span ID (16 hex characters)."""
    return secrets.token_hex(8)


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    return _trace_id.get()


def get_span_id() -> Optional[str]:
    """Get current span ID from context."""
    return _span_id.get()


def get_parent_span_id() -> Optional[str]:
    """Get parent span ID from context."""
    return _parent_span_id.get()


def set_trace_id(trace_id: str) -> contextvars.Token:
    """Set trace ID in context. Returns token for reset."""
    return _trace_id.set(trace_id)


def set_span_id(span_id: str) -> contextvars.Token:
    """Set span ID in context. Returns token for reset."""
    return _span_id.set(span_id)


def set_parent_span_id(parent_span_id: Optional[str]) -> contextvars.Token:
    """Set parent span ID in context. Returns token for reset."""
    return _parent_span_id.set(parent_span_id)


def get_or_create_trace_id() -> str:
    """
    Get current trace ID or create a new one.

    Use this at entry points (middleware) to ensure trace_id exists.
    """
    trace_id = _trace_id.get()
    if trace_id is None:
        trace_id = generate_trace_id()
        _trace_id.set(trace_id)
    return trace_id


def get_trace_context() -> dict:
    """
    Get current trace context as dictionary.

    Useful for logging and passing context to external calls.
    """
    return {
        "trace_id": _trace_id.get(),
        "span_id": _span_id.get(),
        "parent_span_id": _parent_span_id.get(),
    }


def clear_trace_context() -> None:
    """Clear all trace context variables."""
    _trace_id.set(None)
    _span_id.set(None)
    _parent_span_id.set(None)


class SpanContext:
    """
    Context manager for creating nested spans.

    Example:
        with SpanContext() as span_id:
            # span_id is set, parent_span_id is previous span
            await do_work()
    """

    def __init__(self):
        self.span_id = generate_span_id()
        self.previous_span_id: Optional[str] = None
        self.previous_parent_span_id: Optional[str] = None

    def __enter__(self) -> str:
        # Save current span as parent
        self.previous_span_id = _span_id.get()
        self.previous_parent_span_id = _parent_span_id.get()

        # Set new span, current becomes parent
        _parent_span_id.set(self.previous_span_id)
        _span_id.set(self.span_id)

        return self.span_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous context
        _span_id.set(self.previous_span_id)
        _parent_span_id.set(self.previous_parent_span_id)
        return False


class TraceContext:
    """
    Context manager for setting up complete trace context.

    Use at request entry points to establish trace_id and initial span.

    Example:
        with TraceContext(trace_id="from-header") as ctx:
            # ctx.trace_id and ctx.span_id are set
            await handle_request()
    """

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or generate_trace_id()
        self.span_id = generate_span_id()
        self._tokens: list = []

    def __enter__(self) -> "TraceContext":
        self._tokens = [
            _trace_id.set(self.trace_id),
            _span_id.set(self.span_id),
            _parent_span_id.set(None),
        ]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reset to previous values
        _trace_id.reset(self._tokens[0])
        _span_id.reset(self._tokens[1])
        _parent_span_id.reset(self._tokens[2])
        return False
