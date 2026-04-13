"""
OpenTelemetry Configuration
===========================

Centralized configuration for OpenTelemetry SDK.
Supports multiple exporters: OTLP, Console, Redis (custom).
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

from ..models import ServiceName


@dataclass
class TracingConfig:
    """Configuration for OpenTelemetry tracing."""

    service_name: str = "jarvis"
    service_version: str = "1.0.0"

    # Redis exporter (for jarvis-admin SSE)
    redis_url: str = "redis://localhost:6379"
    redis_channel: str = "jarvis:traces"
    redis_enabled: bool = True

    # OTLP exporter (for Jaeger, Grafana Tempo, etc.)
    otlp_endpoint: Optional[str] = None  # e.g., "http://localhost:4317"
    otlp_enabled: bool = False

    # Console exporter (for debugging)
    console_enabled: bool = False

    # Sampling
    sample_rate: float = 1.0  # 1.0 = 100% of traces


_tracer_provider: Optional[TracerProvider] = None


def configure_tracing(
    config: TracingConfig,
    additional_processors: Sequence[SpanProcessor] = (),
) -> TracerProvider:
    """
    Configure OpenTelemetry tracing with specified exporters.

    Args:
        config: Tracing configuration
        additional_processors: Extra span processors to add

    Returns:
        Configured TracerProvider

    Example:
        config = TracingConfig(
            service_name="jarvis-backend",
            redis_enabled=True,
            otlp_endpoint="http://jaeger:4317",
            otlp_enabled=True,
        )
        provider = configure_tracing(config)
    """
    global _tracer_provider

    # Create resource with service info
    resource = Resource.create({
        SERVICE_NAME: config.service_name,
        SERVICE_VERSION: config.service_version,
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add Redis exporter (for backward compatibility with jarvis-admin)
    if config.redis_enabled:
        from .exporter import RedisSpanExporter
        redis_exporter = RedisSpanExporter(
            redis_url=config.redis_url,
            channel=config.redis_channel,
        )
        provider.add_span_processor(BatchSpanProcessor(redis_exporter))

    # Add OTLP exporter (for Jaeger, Grafana Tempo, etc.)
    if config.otlp_enabled and config.otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            import logging
            logging.warning(
                "OTLP exporter requested but opentelemetry-exporter-otlp not installed. "
                "Install with: pip install opentelemetry-exporter-otlp"
            )

    # Add console exporter (for debugging)
    if config.console_enabled:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Add any additional processors
    for processor in additional_processors:
        provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    _tracer_provider = provider

    return provider


def get_tracer(name: str = "jarvis") -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)


def get_tracer_provider() -> Optional[TracerProvider]:
    """Get the configured tracer provider."""
    return _tracer_provider
