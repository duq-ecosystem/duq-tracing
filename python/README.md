# Jarvis Tracing (Python)

Distributed tracing library for Jarvis services.

## Installation

```bash
# Basic installation (legacy Redis-only tracing)
pip install jarvis-tracing

# With OpenTelemetry support (recommended)
pip install jarvis-tracing[otel]

# With OTLP exporter (for Jaeger, Grafana Tempo, etc.)
pip install jarvis-tracing[all]
```

## Quick Start

### Legacy API (Redis Pub/Sub only)

```python
from jarvis_tracing import TracePublisher, TracingMiddleware, ServiceName

publisher = TracePublisher(redis_url="redis://localhost:6379")
await publisher.connect()

app.add_middleware(
    TracingMiddleware,
    publisher=publisher,
    service=ServiceName.BACKEND,
)
```

### OpenTelemetry API (Recommended)

```python
from jarvis_tracing.otel import (
    configure_tracing,
    TracingConfig,
    TracingMiddleware,
    traced,
    ServiceName,
)

# Configure once at startup
config = TracingConfig(
    service_name="jarvis-backend",
    redis_enabled=True,           # For jarvis-admin SSE (backward compat)
    otlp_endpoint="http://jaeger:4317",  # Optional: for Jaeger/Grafana
    otlp_enabled=True,
)
configure_tracing(config)

# Add middleware
app.add_middleware(TracingMiddleware, service=ServiceName.BACKEND)

# Use decorators
@traced("llm_call")
async def call_llm(prompt: str) -> str:
    return await client.messages.create(...)
```

## Migration Guide

The OpenTelemetry-based API (`jarvis_tracing.otel`) is a drop-in replacement:

| Legacy | OpenTelemetry |
|--------|---------------|
| `from jarvis_tracing import ...` | `from jarvis_tracing.otel import ...` |
| `TracePublisher(redis_url=...)` | `configure_tracing(TracingConfig(...))` |
| `X-Trace-ID` header | `traceparent` (W3C) + `X-Trace-ID` (legacy) |

Benefits of OpenTelemetry:
- Industry standard (W3C Trace Context)
- Compatible with Jaeger, Grafana Tempo, Datadog, etc.
- Better tooling and ecosystem
- Still supports Redis Pub/Sub for jarvis-admin

## See Also

- [Main README](../README.md)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
