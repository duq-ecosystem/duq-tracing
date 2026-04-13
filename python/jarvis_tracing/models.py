"""
Trace Event Models
==================

Pydantic models for distributed tracing events.
This is the unified contract for all Jarvis services.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ServiceName(str, Enum):
    """Service identifiers."""
    GATEWAY = "gateway"
    BACKEND = "backend"
    ADMIN = "admin"


class TraceStatus(str, Enum):
    """Trace event status."""
    STARTED = "started"
    SUCCESS = "success"
    ERROR = "error"


class TraceEvent(BaseModel):
    """
    Unified trace event schema.

    All services emit events conforming to this schema.
    Events are published to Redis Pub/Sub for real-time visualization.

    Example:
        event = TraceEvent(
            trace_id="550e8400-e29b-41d4-a716-446655440000",
            span_id="7a8b9c0d1e2f3456",
            service=ServiceName.BACKEND,
            operation="llm_call",
            status=TraceStatus.SUCCESS,
            duration_ms=1234,
            metadata={"model": "claude-sonnet-4-20250514", "tokens": 1500}
        )
    """

    # Required fields
    trace_id: str = Field(..., description="Root trace identifier (UUID v4)")
    span_id: str = Field(..., description="Unique span identifier (16 hex chars)")
    service: ServiceName = Field(..., description="Service that emitted the event")
    operation: str = Field(..., description="Operation type (e.g., 'llm_call', 'api_request')")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    status: TraceStatus = Field(..., description="Event status")

    # Optional fields
    parent_span_id: Optional[str] = Field(None, description="Parent span for nested operations")
    duration_ms: Optional[int] = Field(None, description="Operation duration in milliseconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Operation-specific data")
    tags: dict[str, str] = Field(default_factory=dict, description="Searchable key-value pairs")
    error: Optional[str] = Field(None, description="Error message if status=error")

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }


# Operation type constants for type safety
class Operations:
    """Standard operation types."""

    # Gateway operations
    HTTP_REQUEST_RECEIVED = "http_request_received"
    TELEGRAM_WEBHOOK = "telegram_webhook"
    PROXY_TO_BACKEND = "proxy_to_backend"
    HTTP_RESPONSE_SENT = "http_response_sent"

    # Backend operations
    API_REQUEST = "api_request"
    LLM_CALL = "llm_call"
    TOOL_EXECUTION = "tool_execution"
    MEMORY_SEARCH = "memory_search"
    MEMORY_STORE = "memory_store"
    OBSIDIAN_READ = "obsidian_read"
    OBSIDIAN_WRITE = "obsidian_write"
    QUEUE_ENQUEUE = "queue_enqueue"
    QUEUE_EXECUTE = "queue_execute"
    EXTERNAL_SERVICE = "external_service"
