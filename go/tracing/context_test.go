package tracing

import (
	"context"
	"strings"
	"testing"
)

func TestGenerateTraceID(t *testing.T) {
	traceID := GenerateTraceID()

	// Should be UUID format: 8-4-4-4-12
	parts := strings.Split(traceID, "-")
	if len(parts) != 5 {
		t.Errorf("expected 5 parts, got %d", len(parts))
	}
	if len(parts[0]) != 8 {
		t.Errorf("first part should be 8 chars, got %d", len(parts[0]))
	}
	if len(parts[4]) != 12 {
		t.Errorf("last part should be 12 chars, got %d", len(parts[4]))
	}
}

func TestGenerateTraceIDUnique(t *testing.T) {
	ids := make(map[string]bool)
	for i := 0; i < 100; i++ {
		id := GenerateTraceID()
		if ids[id] {
			t.Error("generated duplicate trace ID")
		}
		ids[id] = true
	}
}

func TestGenerateSpanID(t *testing.T) {
	spanID := GenerateSpanID()

	if len(spanID) != 16 {
		t.Errorf("expected 16 chars, got %d", len(spanID))
	}

	// Should be valid hex
	for _, c := range spanID {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
			t.Errorf("invalid hex character: %c", c)
		}
	}
}

func TestGenerateSpanIDUnique(t *testing.T) {
	ids := make(map[string]bool)
	for i := 0; i < 100; i++ {
		id := GenerateSpanID()
		if ids[id] {
			t.Error("generated duplicate span ID")
		}
		ids[id] = true
	}
}

func TestGetTraceIDEmpty(t *testing.T) {
	ctx := context.Background()
	traceID := GetTraceID(ctx)

	if traceID != "" {
		t.Errorf("expected empty string, got %q", traceID)
	}
}

func TestWithTraceID(t *testing.T) {
	ctx := context.Background()
	ctx = WithTraceID(ctx, "test-trace-id")

	if GetTraceID(ctx) != "test-trace-id" {
		t.Error("trace ID not stored correctly")
	}
}

func TestGetSpanIDEmpty(t *testing.T) {
	ctx := context.Background()
	spanID := GetSpanID(ctx)

	if spanID != "" {
		t.Errorf("expected empty string, got %q", spanID)
	}
}

func TestWithSpanID(t *testing.T) {
	ctx := context.Background()
	ctx = WithSpanID(ctx, "test-span-id")

	if GetSpanID(ctx) != "test-span-id" {
		t.Error("span ID not stored correctly")
	}
}

func TestGetParentSpanIDEmpty(t *testing.T) {
	ctx := context.Background()
	parentSpanID := GetParentSpanID(ctx)

	if parentSpanID != "" {
		t.Errorf("expected empty string, got %q", parentSpanID)
	}
}

func TestWithParentSpanID(t *testing.T) {
	ctx := context.Background()
	ctx = WithParentSpanID(ctx, "parent-span-id")

	if GetParentSpanID(ctx) != "parent-span-id" {
		t.Error("parent span ID not stored correctly")
	}
}

func TestGetOrCreateTraceIDCreatesNew(t *testing.T) {
	ctx := context.Background()
	ctx, traceID := GetOrCreateTraceID(ctx)

	if traceID == "" {
		t.Error("should have created trace ID")
	}
	if GetTraceID(ctx) != traceID {
		t.Error("trace ID not stored in context")
	}
}

func TestGetOrCreateTraceIDReturnsExisting(t *testing.T) {
	ctx := context.Background()
	ctx = WithTraceID(ctx, "existing-trace")

	ctx, traceID := GetOrCreateTraceID(ctx)

	if traceID != "existing-trace" {
		t.Errorf("expected existing-trace, got %q", traceID)
	}
}

func TestWithTraceContext(t *testing.T) {
	ctx := context.Background()
	ctx = WithTraceContext(ctx, "my-trace")

	traceID := GetTraceID(ctx)
	spanID := GetSpanID(ctx)

	if traceID != "my-trace" {
		t.Errorf("expected my-trace, got %q", traceID)
	}
	if spanID == "" {
		t.Error("span ID should be generated")
	}
	if len(spanID) != 16 {
		t.Errorf("span ID should be 16 chars, got %d", len(spanID))
	}
}

func TestWithTraceContextGeneratesTraceID(t *testing.T) {
	ctx := context.Background()
	ctx = WithTraceContext(ctx, "")

	traceID := GetTraceID(ctx)
	if traceID == "" {
		t.Error("trace ID should be generated")
	}
}

func TestStartSpan(t *testing.T) {
	ctx := context.Background()
	ctx = WithTraceID(ctx, "trace-123")
	ctx = WithSpanID(ctx, "original-span")

	ctx = StartSpan(ctx)

	newSpanID := GetSpanID(ctx)
	parentSpanID := GetParentSpanID(ctx)

	if newSpanID == "original-span" {
		t.Error("span ID should be changed")
	}
	if newSpanID == "" {
		t.Error("new span ID should be generated")
	}
	if parentSpanID != "original-span" {
		t.Errorf("expected original-span as parent, got %q", parentSpanID)
	}
	// Trace ID should be preserved
	if GetTraceID(ctx) != "trace-123" {
		t.Error("trace ID should be preserved")
	}
}

func TestGetTraceContext(t *testing.T) {
	ctx := context.Background()
	ctx = WithTraceID(ctx, "trace-123")
	ctx = WithSpanID(ctx, "span-456")
	ctx = WithParentSpanID(ctx, "parent-789")

	traceCtx := GetTraceContext(ctx)

	if traceCtx["trace_id"] != "trace-123" {
		t.Error("trace_id mismatch")
	}
	if traceCtx["span_id"] != "span-456" {
		t.Error("span_id mismatch")
	}
	if traceCtx["parent_span_id"] != "parent-789" {
		t.Error("parent_span_id mismatch")
	}
}

func TestHeaderConstants(t *testing.T) {
	if TraceIDHeader != "X-Trace-ID" {
		t.Errorf("expected X-Trace-ID, got %q", TraceIDHeader)
	}
	if SpanIDHeader != "X-Span-ID" {
		t.Errorf("expected X-Span-ID, got %q", SpanIDHeader)
	}
}
