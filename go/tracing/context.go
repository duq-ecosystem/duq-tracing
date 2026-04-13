package tracing

import (
	"context"
	"crypto/rand"
	"encoding/hex"

	"github.com/google/uuid"
)

// Context keys for trace propagation.
type contextKey string

const (
	traceIDKey      contextKey = "trace_id"
	spanIDKey       contextKey = "span_id"
	parentSpanIDKey contextKey = "parent_span_id"
)

// Header names for HTTP propagation.
const (
	TraceIDHeader = "X-Trace-ID"
	SpanIDHeader  = "X-Span-ID"
)

// GenerateTraceID creates a new trace ID (UUID v4).
func GenerateTraceID() string {
	return uuid.New().String()
}

// GenerateSpanID creates a new span ID (16 hex characters).
func GenerateSpanID() string {
	b := make([]byte, 8)
	rand.Read(b)
	return hex.EncodeToString(b)
}

// GetTraceID returns the trace ID from context.
func GetTraceID(ctx context.Context) string {
	if v := ctx.Value(traceIDKey); v != nil {
		return v.(string)
	}
	return ""
}

// GetSpanID returns the span ID from context.
func GetSpanID(ctx context.Context) string {
	if v := ctx.Value(spanIDKey); v != nil {
		return v.(string)
	}
	return ""
}

// GetParentSpanID returns the parent span ID from context.
func GetParentSpanID(ctx context.Context) string {
	if v := ctx.Value(parentSpanIDKey); v != nil {
		return v.(string)
	}
	return ""
}

// WithTraceID returns a new context with the trace ID set.
func WithTraceID(ctx context.Context, traceID string) context.Context {
	return context.WithValue(ctx, traceIDKey, traceID)
}

// WithSpanID returns a new context with the span ID set.
func WithSpanID(ctx context.Context, spanID string) context.Context {
	return context.WithValue(ctx, spanIDKey, spanID)
}

// WithParentSpanID returns a new context with the parent span ID set.
func WithParentSpanID(ctx context.Context, parentSpanID string) context.Context {
	return context.WithValue(ctx, parentSpanIDKey, parentSpanID)
}

// GetOrCreateTraceID returns the trace ID from context or creates a new one.
func GetOrCreateTraceID(ctx context.Context) (context.Context, string) {
	if traceID := GetTraceID(ctx); traceID != "" {
		return ctx, traceID
	}
	traceID := GenerateTraceID()
	return WithTraceID(ctx, traceID), traceID
}

// WithTraceContext returns a new context with complete trace context.
// If traceID is empty, a new one is generated.
func WithTraceContext(ctx context.Context, traceID string) context.Context {
	if traceID == "" {
		traceID = GenerateTraceID()
	}
	spanID := GenerateSpanID()

	ctx = WithTraceID(ctx, traceID)
	ctx = WithSpanID(ctx, spanID)
	return ctx
}

// StartSpan creates a new span within the current trace.
// The current span becomes the parent of the new span.
func StartSpan(ctx context.Context) context.Context {
	currentSpanID := GetSpanID(ctx)
	newSpanID := GenerateSpanID()

	ctx = WithParentSpanID(ctx, currentSpanID)
	ctx = WithSpanID(ctx, newSpanID)
	return ctx
}

// GetTraceContext returns trace context as a map.
// Useful for logging and debugging.
func GetTraceContext(ctx context.Context) map[string]string {
	return map[string]string{
		"trace_id":       GetTraceID(ctx),
		"span_id":        GetSpanID(ctx),
		"parent_span_id": GetParentSpanID(ctx),
	}
}
