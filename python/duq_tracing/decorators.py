"""
Tracing Decorators
==================

Decorators for automatic function tracing.
Simplifies adding tracing to existing code.
"""

import asyncio
import functools
import time
from typing import Any, Callable, Optional, TypeVar, Union

from .context import SpanContext, get_parent_span_id, get_span_id, get_trace_id
from .models import ServiceName, TraceEvent, TraceStatus
from .publisher import get_publisher

F = TypeVar("F", bound=Callable[..., Any])


def traced(
    operation: str,
    service: ServiceName = ServiceName.BACKEND,
    capture_args: bool = False,
    capture_result: bool = False,
) -> Callable[[F], F]:
    """
    Decorator for tracing async functions.

    Automatically publishes start/end events with duration tracking.

    Args:
        operation: Operation name (e.g., "llm_call", "obsidian_read")
        service: Service that owns this operation
        capture_args: Whether to include function args in metadata
        capture_result: Whether to include return value in metadata

    Example:
        @traced("llm_call", capture_args=False)
        async def call_anthropic(model: str, messages: list):
            ...

        @traced("obsidian_read", service=ServiceName.BACKEND)
        async def read_note(path: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            publisher = get_publisher()

            # If no publisher or no trace context, just call function
            trace_id = get_trace_id()
            if not publisher or not trace_id:
                return await func(*args, **kwargs)

            # Create new span
            with SpanContext() as span_id:
                start_time = time.perf_counter()
                metadata: dict[str, Any] = {}
                error_msg: Optional[str] = None

                # Capture args if requested
                if capture_args:
                    # Be careful with large args
                    metadata["args"] = _safe_repr(args[:3])  # First 3 args
                    metadata["kwargs"] = _safe_repr(
                        {k: v for k, v in list(kwargs.items())[:5]}
                    )

                # Publish start event
                start_event = TraceEvent(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=get_parent_span_id(),
                    service=service,
                    operation=operation,
                    status=TraceStatus.STARTED,
                    metadata=metadata.copy(),
                )
                await publisher.publish(start_event)

                try:
                    # Execute function
                    result = await func(*args, **kwargs)

                    # Capture result if requested
                    if capture_result:
                        metadata["result"] = _safe_repr(result)

                    return result

                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    raise

                finally:
                    # Calculate duration
                    duration_ms = int((time.perf_counter() - start_time) * 1000)

                    # Publish end event
                    end_event = TraceEvent(
                        trace_id=trace_id,
                        span_id=span_id,
                        parent_span_id=get_parent_span_id(),
                        service=service,
                        operation=operation,
                        status=TraceStatus.ERROR if error_msg else TraceStatus.SUCCESS,
                        duration_ms=duration_ms,
                        metadata=metadata,
                        error=error_msg,
                    )
                    # Fire and forget - don't block on publish
                    asyncio.create_task(publisher.publish(end_event))

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, just call without tracing
            # (tracing is async, sync functions should use manual tracing)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def _safe_repr(obj: Any, max_len: int = 500) -> str:
    """
    Safe string representation with size limit.

    Prevents huge payloads from bloating trace events.
    """
    try:
        s = repr(obj)
        if len(s) > max_len:
            return s[: max_len - 3] + "..."
        return s
    except Exception:
        return "<unrepresentable>"


class TracedClass:
    """
    Mixin for adding tracing to all async methods of a class.

    Example:
        class LLMClient(TracedClass):
            _trace_service = ServiceName.BACKEND
            _trace_operations = {
                "create_message": "llm_call",
                "stream_message": "llm_stream",
            }

            async def create_message(self, ...):
                ...
    """

    _trace_service: ServiceName = ServiceName.BACKEND
    _trace_operations: dict[str, str] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        for method_name, operation in cls._trace_operations.items():
            if hasattr(cls, method_name):
                original = getattr(cls, method_name)
                if asyncio.iscoroutinefunction(original):
                    decorated = traced(operation, cls._trace_service)(original)
                    setattr(cls, method_name, decorated)
