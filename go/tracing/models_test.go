package tracing

import (
	"encoding/json"
	"testing"
	"time"
)

func TestServiceNameConstants(t *testing.T) {
	tests := []struct {
		name     string
		constant ServiceName
		expected string
	}{
		{"Gateway", ServiceGateway, "gateway"},
		{"Backend", ServiceBackend, "backend"},
		{"Admin", ServiceAdmin, "admin"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if string(tt.constant) != tt.expected {
				t.Errorf("expected %q, got %q", tt.expected, string(tt.constant))
			}
		})
	}
}

func TestTraceStatusConstants(t *testing.T) {
	tests := []struct {
		name     string
		constant TraceStatus
		expected string
	}{
		{"Started", StatusStarted, "started"},
		{"Success", StatusSuccess, "success"},
		{"Error", StatusError, "error"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if string(tt.constant) != tt.expected {
				t.Errorf("expected %q, got %q", tt.expected, string(tt.constant))
			}
		})
	}
}

func TestOperationsConstants(t *testing.T) {
	if Operations.HTTPRequestReceived != "http_request_received" {
		t.Error("HTTPRequestReceived mismatch")
	}
	if Operations.LLMCall != "llm_call" {
		t.Error("LLMCall mismatch")
	}
	if Operations.ToolExecution != "tool_execution" {
		t.Error("ToolExecution mismatch")
	}
	if Operations.MemorySearch != "memory_search" {
		t.Error("MemorySearch mismatch")
	}
}

func TestNewTraceEvent(t *testing.T) {
	event := NewTraceEvent("trace-123", "span-456", ServiceBackend, "test_op", StatusSuccess)

	if event.TraceID != "trace-123" {
		t.Errorf("expected trace-123, got %s", event.TraceID)
	}
	if event.SpanID != "span-456" {
		t.Errorf("expected span-456, got %s", event.SpanID)
	}
	if event.Service != ServiceBackend {
		t.Errorf("expected backend, got %s", event.Service)
	}
	if event.Operation != "test_op" {
		t.Errorf("expected test_op, got %s", event.Operation)
	}
	if event.Status != StatusSuccess {
		t.Errorf("expected success, got %s", event.Status)
	}
	if event.Metadata == nil {
		t.Error("Metadata should be initialized")
	}
	if event.Tags == nil {
		t.Error("Tags should be initialized")
	}
}

func TestTraceEventSetParentSpan(t *testing.T) {
	event := NewTraceEvent("trace", "span", ServiceGateway, "op", StatusStarted)
	event.SetParentSpan("parent-span")

	if event.ParentSpanID != "parent-span" {
		t.Errorf("expected parent-span, got %s", event.ParentSpanID)
	}
}

func TestTraceEventSetDuration(t *testing.T) {
	event := NewTraceEvent("trace", "span", ServiceGateway, "op", StatusSuccess)
	event.SetDuration(1234)

	if event.DurationMs == nil {
		t.Fatal("DurationMs should not be nil")
	}
	if *event.DurationMs != 1234 {
		t.Errorf("expected 1234, got %d", *event.DurationMs)
	}
}

func TestTraceEventSetError(t *testing.T) {
	event := NewTraceEvent("trace", "span", ServiceBackend, "op", StatusStarted)
	event.SetError("something went wrong")

	if event.Error != "something went wrong" {
		t.Errorf("expected error message, got %s", event.Error)
	}
	if event.Status != StatusError {
		t.Errorf("expected error status, got %s", event.Status)
	}
}

func TestTraceEventAddMetadata(t *testing.T) {
	event := NewTraceEvent("trace", "span", ServiceBackend, "op", StatusSuccess)
	event.AddMetadata("key1", "value1")
	event.AddMetadata("key2", 123)

	if event.Metadata["key1"] != "value1" {
		t.Error("key1 not found in metadata")
	}
	if event.Metadata["key2"] != 123 {
		t.Error("key2 not found in metadata")
	}
}

func TestTraceEventAddTag(t *testing.T) {
	event := NewTraceEvent("trace", "span", ServiceBackend, "op", StatusSuccess)
	event.AddTag("env", "test")
	event.AddTag("version", "1.0")

	if event.Tags["env"] != "test" {
		t.Error("env tag not found")
	}
	if event.Tags["version"] != "1.0" {
		t.Error("version tag not found")
	}
}

func TestTraceEventToJSON(t *testing.T) {
	event := NewTraceEvent("trace-123", "span-456", ServiceBackend, "test_op", StatusSuccess)

	jsonBytes, err := event.ToJSON()
	if err != nil {
		t.Fatalf("ToJSON failed: %v", err)
	}

	var parsed map[string]any
	err = json.Unmarshal(jsonBytes, &parsed)
	if err != nil {
		t.Fatalf("Failed to parse JSON: %v", err)
	}

	if parsed["trace_id"] != "trace-123" {
		t.Error("trace_id not in JSON")
	}
	if parsed["span_id"] != "span-456" {
		t.Error("span_id not in JSON")
	}
	if parsed["service"] != "backend" {
		t.Error("service not in JSON")
	}
}

func TestTraceEventChainedBuilders(t *testing.T) {
	event := NewTraceEvent("trace", "span", ServiceGateway, "http_request", StatusSuccess).
		SetParentSpan("parent").
		SetDuration(100).
		AddMetadata("path", "/api/test").
		AddTag("method", "GET")

	if event.ParentSpanID != "parent" {
		t.Error("ParentSpanID not set")
	}
	if event.DurationMs == nil || *event.DurationMs != 100 {
		t.Error("DurationMs not set")
	}
	if event.Metadata["path"] != "/api/test" {
		t.Error("Metadata not set")
	}
	if event.Tags["method"] != "GET" {
		t.Error("Tags not set")
	}
}

func TestTraceEventTimestamp(t *testing.T) {
	before := time.Now().UTC()
	event := NewTraceEvent("trace", "span", ServiceBackend, "op", StatusStarted)
	after := time.Now().UTC()

	if event.Timestamp.Before(before) || event.Timestamp.After(after) {
		t.Error("Timestamp should be between before and after")
	}
}
