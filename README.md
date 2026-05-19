# ⛔ ЛОКАЛЬНОЕ ТЕСТИРОВАНИЕ ЗАПРЕЩЕНО - ТОЛЬКО VPS 90.156.230.49 ⛔


# Duq Tracing

Distributed tracing library for Duq services. Provides unified tracing across Python and Go services with Redis Pub/Sub transport.

## Features

- UUID v4 trace IDs for request correlation
- Automatic context propagation through async code
- HTTP middleware for FastAPI (Python) and Chi (Go)
- Redis Pub/Sub for real-time event streaming
- Decorators and helpers for easy instrumentation

## Installation

### Python

```bash
pip install -e ./python
```

### Go

```bash
go get github.com/danny/duq-tracing/tracing
```

## Quick Start

### Python

```python
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
```

### Go

```go
import "github.com/danny/duq-tracing/tracing"

// Initialize publisher
cfg := &tracing.PublisherConfig{
    RedisURL: "redis://localhost:6379",
    Channel:  "duq:traces",
    Enabled:  true,
}
publisher, _ := tracing.NewPublisher(cfg)

// Add middleware to Chi router
r := chi.NewRouter()
r.Use(tracing.Middleware(publisher, tracing.ServiceGateway))

// Manual spans
span := publisher.StartSpan(ctx, "proxy_to_backend", tracing.ServiceGateway)
defer span.Finish()
```

## Trace Event Schema

All events conform to this JSON schema:

```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "span_id": "7a8b9c0d1e2f3456",
  "parent_span_id": "1234567890abcdef",
  "service": "backend",
  "operation": "llm_call",
  "timestamp": "2026-04-08T12:34:56.789Z",
  "duration_ms": 1234,
  "status": "success",
  "metadata": {},
  "tags": {},
  "error": null
}
```

## Configuration

Environment variables:

- `REDIS_URL` - Redis connection URL (default: `redis://localhost:6379`)
- `TRACE_CHANNEL` - Redis Pub/Sub channel (default: `duq:traces`)
- `TRACING_ENABLED` - Enable/disable tracing (default: `true`)

## License

MIT
