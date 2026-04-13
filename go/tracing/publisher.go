package tracing

import (
	"context"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

// Publisher publishes trace events to Redis Pub/Sub.
type Publisher struct {
	client  *redis.Client
	channel string
	enabled bool
}

// PublisherConfig contains configuration for the Publisher.
type PublisherConfig struct {
	RedisURL string
	Channel  string
	Enabled  bool
}

// DefaultConfig returns default publisher configuration.
func DefaultConfig() *PublisherConfig {
	return &PublisherConfig{
		RedisURL: "redis://localhost:6379",
		Channel:  "jarvis:traces",
		Enabled:  true,
	}
}

// NewPublisher creates a new trace publisher.
func NewPublisher(cfg *PublisherConfig) (*Publisher, error) {
	if cfg == nil {
		cfg = DefaultConfig()
	}

	if !cfg.Enabled {
		return &Publisher{enabled: false}, nil
	}

	opt, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		return nil, err
	}

	client := redis.NewClient(opt)

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, err
	}

	log.Printf("TracePublisher connected to Redis: %s", cfg.RedisURL)

	return &Publisher{
		client:  client,
		channel: cfg.Channel,
		enabled: true,
	}, nil
}

// NewPublisherFromClient creates a publisher from existing Redis client.
func NewPublisherFromClient(client *redis.Client, channel string) *Publisher {
	return &Publisher{
		client:  client,
		channel: channel,
		enabled: true,
	}
}

// Close closes the Redis connection.
func (p *Publisher) Close() error {
	if p.client != nil {
		return p.client.Close()
	}
	return nil
}

// Publish sends a trace event to Redis.
func (p *Publisher) Publish(ctx context.Context, event *TraceEvent) error {
	if !p.enabled || p.client == nil {
		return nil
	}

	data, err := event.ToJSON()
	if err != nil {
		return err
	}

	return p.client.Publish(ctx, p.channel, data).Err()
}

// PublishStart publishes a "started" event for an operation.
// Returns the span ID for tracking.
func (p *Publisher) PublishStart(
	ctx context.Context,
	operation string,
	service ServiceName,
	metadata map[string]any,
	tags map[string]string,
) string {
	traceID := GetTraceID(ctx)
	if traceID == "" {
		return ""
	}

	spanID := GetSpanID(ctx)
	if spanID == "" {
		spanID = GenerateSpanID()
	}

	event := NewTraceEvent(traceID, spanID, service, operation, StatusStarted).
		SetParentSpan(GetParentSpanID(ctx))

	for k, v := range metadata {
		event.AddMetadata(k, v)
	}
	for k, v := range tags {
		event.AddTag(k, v)
	}

	if err := p.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish trace start: %v", err)
	}

	return spanID
}

// PublishEnd publishes a completion event.
func (p *Publisher) PublishEnd(
	ctx context.Context,
	operation string,
	service ServiceName,
	spanID string,
	status TraceStatus,
	durationMs int,
	metadata map[string]any,
	tags map[string]string,
	errorMsg string,
) {
	traceID := GetTraceID(ctx)
	if traceID == "" {
		return
	}

	event := NewTraceEvent(traceID, spanID, service, operation, status).
		SetParentSpan(GetParentSpanID(ctx)).
		SetDuration(durationMs)

	if errorMsg != "" {
		event.SetError(errorMsg)
	}

	for k, v := range metadata {
		event.AddMetadata(k, v)
	}
	for k, v := range tags {
		event.AddTag(k, v)
	}

	if err := p.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish trace end: %v", err)
	}
}

// Span represents an active trace span for convenient timing.
type Span struct {
	publisher  *Publisher
	ctx        context.Context
	operation  string
	service    ServiceName
	spanID     string
	startTime  time.Time
	metadata   map[string]any
	tags       map[string]string
	errorMsg   string
	isFinished bool
}

// StartSpan creates and publishes a new span.
func (p *Publisher) StartSpan(ctx context.Context, operation string, service ServiceName) *Span {
	spanID := p.PublishStart(ctx, operation, service, nil, nil)

	return &Span{
		publisher: p,
		ctx:       ctx,
		operation: operation,
		service:   service,
		spanID:    spanID,
		startTime: time.Now(),
		metadata:  make(map[string]any),
		tags:      make(map[string]string),
	}
}

// AddMetadata adds metadata to the span.
func (s *Span) AddMetadata(key string, value any) *Span {
	s.metadata[key] = value
	return s
}

// AddTag adds a tag to the span.
func (s *Span) AddTag(key, value string) *Span {
	s.tags[key] = value
	return s
}

// SetError marks the span as failed.
func (s *Span) SetError(err error) *Span {
	if err != nil {
		s.errorMsg = err.Error()
	}
	return s
}

// Finish completes the span and publishes the end event.
func (s *Span) Finish() {
	if s.isFinished {
		return
	}
	s.isFinished = true

	durationMs := int(time.Since(s.startTime).Milliseconds())
	status := StatusSuccess
	if s.errorMsg != "" {
		status = StatusError
	}

	s.publisher.PublishEnd(
		s.ctx,
		s.operation,
		s.service,
		s.spanID,
		status,
		durationMs,
		s.metadata,
		s.tags,
		s.errorMsg,
	)
}

// FinishWithError completes the span with an error.
func (s *Span) FinishWithError(err error) {
	s.SetError(err)
	s.Finish()
}
