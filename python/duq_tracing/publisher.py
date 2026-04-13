"""
Trace Publisher
===============

Async Redis publisher for trace events.
Publishes events to Redis Pub/Sub channel for real-time consumption.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from .context import (
    SpanContext,
    generate_span_id,
    get_parent_span_id,
    get_span_id,
    get_trace_id,
)
from .models import Operations, ServiceName, TraceEvent, TraceStatus

logger = logging.getLogger(__name__)


class TracePublisher:
    """
    Async trace event publisher using Redis Pub/Sub.

    Example:
        publisher = TracePublisher(redis_url="redis://localhost:6379")
        await publisher.connect()

        await publisher.publish(TraceEvent(
            trace_id="...",
            span_id="...",
            service=ServiceName.BACKEND,
            operation="llm_call",
            status=TraceStatus.SUCCESS
        ))

        await publisher.close()
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        channel: str = "duq:traces",
        enabled: bool = True,
    ):
        self.redis_url = redis_url
        self.channel = channel
        self.enabled = enabled
        self._redis = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if not self.enabled:
            return

        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(self.redis_url)
            # Test connection
            await self._redis.ping()
            logger.info("TracePublisher connected to Redis: %s", self.redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            self._redis = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def publish(self, event: TraceEvent) -> bool:
        """
        Publish a trace event to Redis channel.

        Returns True if published successfully, False otherwise.
        """
        if not self.enabled or not self._redis:
            return False

        try:
            message = event.model_dump_json()
            await self._redis.publish(self.channel, message)
            logger.debug("Published trace event: %s %s", event.operation, event.span_id)
            return True
        except Exception as e:
            logger.error("Failed to publish trace event: %s", e)
            return False

    async def publish_start(
        self,
        operation: str,
        service: ServiceName,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Publish a "started" event for an operation.

        Returns the span_id for tracking, or None if publishing failed.
        Uses current trace context.
        """
        trace_id = get_trace_id()
        if not trace_id:
            logger.warning("No trace_id in context for %s", operation)
            return None

        span_id = get_span_id() or generate_span_id()

        event = TraceEvent(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=get_parent_span_id(),
            service=service,
            operation=operation,
            status=TraceStatus.STARTED,
            metadata=metadata or {},
            tags=tags or {},
        )

        await self.publish(event)
        return span_id

    async def publish_end(
        self,
        operation: str,
        service: ServiceName,
        span_id: str,
        status: TraceStatus,
        duration_ms: int,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[dict[str, str]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        Publish a completion event (success or error).
        """
        trace_id = get_trace_id()
        if not trace_id:
            return False

        event = TraceEvent(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=get_parent_span_id(),
            service=service,
            operation=operation,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata or {},
            tags=tags or {},
            error=error,
        )

        return await self.publish(event)


class TracedOperation:
    """
    Async context manager for tracing an operation.

    Automatically publishes start/end events and tracks duration.

    Example:
        async with TracedOperation(
            publisher, "llm_call", ServiceName.BACKEND,
            metadata={"model": "claude-sonnet"}
        ) as span:
            result = await call_llm()
            span.add_metadata("tokens", 1500)
    """

    def __init__(
        self,
        publisher: TracePublisher,
        operation: str,
        service: ServiceName,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[dict[str, str]] = None,
    ):
        self.publisher = publisher
        self.operation = operation
        self.service = service
        self.metadata = metadata or {}
        self.tags = tags or {}
        self.span_context = SpanContext()
        self.span_id: Optional[str] = None
        self.start_time: Optional[float] = None
        self.error: Optional[str] = None

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata during operation execution."""
        self.metadata[key] = value

    def add_tag(self, key: str, value: str) -> None:
        """Add tag during operation execution."""
        self.tags[key] = value

    def set_error(self, error: str) -> None:
        """Mark operation as failed with error message."""
        self.error = error

    async def __aenter__(self) -> "TracedOperation":
        import time

        # Enter span context
        self.span_id = self.span_context.__enter__()
        self.start_time = time.perf_counter()

        # Publish start event
        await self.publisher.publish_start(
            self.operation,
            self.service,
            metadata=self.metadata.copy(),
            tags=self.tags.copy(),
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        import time

        # Calculate duration
        duration_ms = int((time.perf_counter() - self.start_time) * 1000)

        # Determine status
        if exc_val is not None:
            status = TraceStatus.ERROR
            self.error = str(exc_val)
        elif self.error:
            status = TraceStatus.ERROR
        else:
            status = TraceStatus.SUCCESS

        # Publish end event
        await self.publisher.publish_end(
            self.operation,
            self.service,
            self.span_id,
            status,
            duration_ms,
            metadata=self.metadata,
            tags=self.tags,
            error=self.error,
        )

        # Exit span context
        self.span_context.__exit__(exc_type, exc_val, exc_tb)

        return False  # Don't suppress exceptions


# Global publisher instance (set during app initialization)
_publisher: Optional[TracePublisher] = None


def get_publisher() -> Optional[TracePublisher]:
    """Get the global trace publisher."""
    return _publisher


def set_publisher(publisher: TracePublisher) -> None:
    """Set the global trace publisher."""
    global _publisher
    _publisher = publisher
