"""
Redis Span Exporter
===================

Custom OpenTelemetry exporter that publishes spans to Redis Pub/Sub.
Maintains backward compatibility with jarvis-admin SSE streaming.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Sequence, Optional, Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

from ..models import TraceStatus

logger = logging.getLogger(__name__)


class RedisSpanExporter(SpanExporter):
    """
    Exports OpenTelemetry spans to Redis Pub/Sub.

    Converts OTel spans to the TraceEvent JSON format expected by jarvis-admin.
    This allows gradual migration to OpenTelemetry while keeping existing dashboards.

    Example:
        exporter = RedisSpanExporter(
            redis_url="redis://localhost:6379",
            channel="jarvis:traces"
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        channel: str = "jarvis:traces",
    ):
        self.redis_url = redis_url
        self.channel = channel
        self._redis = None
        self._connected = False

    def _ensure_connected(self) -> bool:
        """Lazy connect to Redis."""
        if self._connected:
            return self._redis is not None

        try:
            import redis
            self._redis = redis.from_url(self.redis_url)
            self._redis.ping()
            self._connected = True
            logger.info("RedisSpanExporter connected to %s", self.redis_url)
            return True
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            self._connected = True  # Mark as attempted
            return False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to Redis Pub/Sub."""
        if not self._ensure_connected():
            return SpanExportResult.FAILURE

        if self._redis is None:
            return SpanExportResult.FAILURE

        try:
            for span in spans:
                event = self._span_to_trace_event(span)
                message = json.dumps(event, default=str)
                self._redis.publish(self.channel, message)

            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.error("Failed to export spans to Redis: %s", e)
            return SpanExportResult.FAILURE

    def _span_to_trace_event(self, span: ReadableSpan) -> dict[str, Any]:
        """
        Convert OpenTelemetry span to TraceEvent JSON.

        Maps OTel concepts to our existing schema:
        - trace_id: OTel trace ID (hex)
        - span_id: OTel span ID (hex)
        - parent_span_id: OTel parent span ID (hex)
        - service: From resource attributes or span attributes
        - operation: Span name
        - status: Mapped from OTel StatusCode
        - duration_ms: Calculated from timestamps
        - metadata: From span attributes
        - tags: From span attributes (string values only)
        """
        # Get IDs as hex strings
        context = span.get_span_context()
        trace_id = format(context.trace_id, "032x")
        span_id = format(context.span_id, "016x")

        parent_span_id = None
        if span.parent is not None:
            parent_span_id = format(span.parent.span_id, "016x")

        # Map status
        status = TraceStatus.SUCCESS
        error_msg = None
        if span.status.status_code == StatusCode.ERROR:
            status = TraceStatus.ERROR
            error_msg = span.status.description
        elif span.status.status_code == StatusCode.UNSET:
            # Check if span ended (has duration)
            if span.end_time is None:
                status = "started"
            else:
                status = TraceStatus.SUCCESS

        # Calculate duration
        duration_ms = None
        if span.start_time and span.end_time:
            duration_ns = span.end_time - span.start_time
            duration_ms = int(duration_ns / 1_000_000)

        # Get service name from resource
        service = "backend"
        if span.resource:
            service = span.resource.attributes.get("service.name", "backend")

        # Extract attributes
        metadata = {}
        tags = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                tags[key] = value
            else:
                metadata[key] = value

        # Get timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        if span.start_time:
            timestamp = datetime.fromtimestamp(
                span.start_time / 1_000_000_000,
                tz=timezone.utc
            ).isoformat()

        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "service": service,
            "operation": span.name,
            "timestamp": timestamp,
            "status": status,
            "duration_ms": duration_ms,
            "metadata": metadata,
            "tags": tags,
            "error": error_msg,
        }

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        if self._redis:
            try:
                self._redis.close()
            except Exception:
                pass
            self._redis = None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush (no-op for sync Redis)."""
        return True
