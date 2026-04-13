"""
OpenTelemetry Tracing Decorators
================================

Function decorators for automatic tracing using OpenTelemetry.
"""

import functools
import inspect
from typing import Any, Callable, Optional, TypeVar, Union

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ..models import ServiceName

F = TypeVar("F", bound=Callable[..., Any])


def traced(
    operation: Optional[str] = None,
    service: ServiceName = ServiceName.BACKEND,
    metadata: Optional[dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator for tracing function execution.

    Works with both sync and async functions.

    Args:
        operation: Operation name (defaults to function name)
        service: Service identifier
        metadata: Static attributes to add to span

    Example:
        @traced("llm_call")
        async def call_llm(prompt: str) -> str:
            return await client.messages.create(...)

        @traced("tool_execution", metadata={"tool_type": "file_op"})
        def read_file(path: str) -> str:
            ...
    """
    def decorator(func: F) -> F:
        span_name = operation or func.__name__
        tracer = trace.get_tracer(f"duq.{service.value}")
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                attributes = {
                    "service": service.value,
                    "function": func.__name__,
                }
                if metadata:
                    attributes.update(metadata)

                with tracer.start_as_current_span(span_name, attributes=attributes) as span:
                    try:
                        result = await func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise

            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                attributes = {
                    "service": service.value,
                    "function": func.__name__,
                }
                if metadata:
                    attributes.update(metadata)

                with tracer.start_as_current_span(span_name, attributes=attributes) as span:
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise

            return sync_wrapper  # type: ignore

    return decorator


class TracedClass:
    """
    Mixin for classes that need tracing on all public methods.

    Automatically traces all public methods (not starting with _).

    Example:
        class LLMClient(TracedClass):
            _service = ServiceName.BACKEND

            async def call(self, prompt: str) -> str:
                # Automatically traced as "LLMClient.call"
                ...
    """

    _service: ServiceName = ServiceName.BACKEND

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        service = getattr(cls, "_service", ServiceName.BACKEND)
        tracer = trace.get_tracer(f"duq.{service.value}")

        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue

            span_name = f"{cls.__name__}.{name}"
            is_async = inspect.iscoroutinefunction(method)

            if is_async:
                @functools.wraps(method)
                async def async_wrapper(
                    self: Any,
                    *args: Any,
                    _original_method: Callable = method,
                    _span_name: str = span_name,
                    _tracer: trace.Tracer = tracer,
                    **kwargs: Any,
                ) -> Any:
                    with _tracer.start_as_current_span(_span_name) as span:
                        try:
                            return await _original_method(self, *args, **kwargs)
                        except Exception as e:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                            raise

                setattr(cls, name, async_wrapper)
            else:
                @functools.wraps(method)
                def sync_wrapper(
                    self: Any,
                    *args: Any,
                    _original_method: Callable = method,
                    _span_name: str = span_name,
                    _tracer: trace.Tracer = tracer,
                    **kwargs: Any,
                ) -> Any:
                    with _tracer.start_as_current_span(_span_name) as span:
                        try:
                            return _original_method(self, *args, **kwargs)
                        except Exception as e:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                            raise

                setattr(cls, name, sync_wrapper)
