// Package tracing provides distributed tracing for Jarvis services.
package tracing

import (
	"encoding/json"
	"time"
)

// ServiceName identifies the service emitting trace events.
type ServiceName string

const (
	ServiceGateway ServiceName = "gateway"
	ServiceBackend ServiceName = "backend"
	ServiceAdmin   ServiceName = "admin"
)

// TraceStatus represents the status of a trace event.
type TraceStatus string

const (
	StatusStarted TraceStatus = "started"
	StatusSuccess TraceStatus = "success"
	StatusError   TraceStatus = "error"
)

// Operations contains standard operation type constants.
var Operations = struct {
	// Gateway operations
	HTTPRequestReceived string
	TelegramWebhook     string
	ProxyToBackend      string
	HTTPResponseSent    string

	// Backend operations
	APIRequest      string
	LLMCall         string
	ToolExecution   string
	MemorySearch    string
	MemoryStore     string
	ObsidianRead    string
	ObsidianWrite   string
	QueueEnqueue    string
	QueueExecute    string
	ExternalService string
}{
	HTTPRequestReceived: "http_request_received",
	TelegramWebhook:     "telegram_webhook",
	ProxyToBackend:      "proxy_to_backend",
	HTTPResponseSent:    "http_response_sent",
	APIRequest:          "api_request",
	LLMCall:             "llm_call",
	ToolExecution:       "tool_execution",
	MemorySearch:        "memory_search",
	MemoryStore:         "memory_store",
	ObsidianRead:        "obsidian_read",
	ObsidianWrite:       "obsidian_write",
	QueueEnqueue:        "queue_enqueue",
	QueueExecute:        "queue_execute",
	ExternalService:     "external_service",
}

// TraceEvent represents a single trace event.
// All services emit events conforming to this schema.
type TraceEvent struct {
	TraceID      string            `json:"trace_id"`
	SpanID       string            `json:"span_id"`
	ParentSpanID string            `json:"parent_span_id,omitempty"`
	Service      ServiceName       `json:"service"`
	Operation    string            `json:"operation"`
	Timestamp    time.Time         `json:"timestamp"`
	DurationMs   *int              `json:"duration_ms,omitempty"`
	Status       TraceStatus       `json:"status"`
	Metadata     map[string]any    `json:"metadata,omitempty"`
	Tags         map[string]string `json:"tags,omitempty"`
	Error        string            `json:"error,omitempty"`
}

// NewTraceEvent creates a new trace event with required fields.
func NewTraceEvent(traceID, spanID string, service ServiceName, operation string, status TraceStatus) *TraceEvent {
	return &TraceEvent{
		TraceID:   traceID,
		SpanID:    spanID,
		Service:   service,
		Operation: operation,
		Timestamp: time.Now().UTC(),
		Status:    status,
		Metadata:  make(map[string]any),
		Tags:      make(map[string]string),
	}
}

// SetParentSpan sets the parent span ID.
func (e *TraceEvent) SetParentSpan(parentSpanID string) *TraceEvent {
	e.ParentSpanID = parentSpanID
	return e
}

// SetDuration sets the operation duration.
func (e *TraceEvent) SetDuration(ms int) *TraceEvent {
	e.DurationMs = &ms
	return e
}

// SetError sets the error message and status.
func (e *TraceEvent) SetError(err string) *TraceEvent {
	e.Error = err
	e.Status = StatusError
	return e
}

// AddMetadata adds a key-value pair to metadata.
func (e *TraceEvent) AddMetadata(key string, value any) *TraceEvent {
	if e.Metadata == nil {
		e.Metadata = make(map[string]any)
	}
	e.Metadata[key] = value
	return e
}

// AddTag adds a key-value pair to tags.
func (e *TraceEvent) AddTag(key, value string) *TraceEvent {
	if e.Tags == nil {
		e.Tags = make(map[string]string)
	}
	e.Tags[key] = value
	return e
}

// ToJSON serializes the event to JSON.
func (e *TraceEvent) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}

// MarshalJSON implements custom JSON marshaling for proper timestamp format.
func (e *TraceEvent) MarshalJSON() ([]byte, error) {
	type Alias TraceEvent
	return json.Marshal(&struct {
		Timestamp string `json:"timestamp"`
		*Alias
	}{
		Timestamp: e.Timestamp.Format(time.RFC3339Nano),
		Alias:     (*Alias)(e),
	})
}
