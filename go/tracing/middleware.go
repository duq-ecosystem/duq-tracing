package tracing

import (
	"net/http"
	"regexp"
	"strings"
	"time"
)

// responseWriter wraps http.ResponseWriter to capture status code.
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func newResponseWriter(w http.ResponseWriter) *responseWriter {
	return &responseWriter{w, http.StatusOK}
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// Middleware returns a Chi-compatible middleware for distributed tracing.
// It extracts or generates trace_id from X-Trace-ID header and publishes
// start/end events for each request.
func Middleware(publisher *Publisher, service ServiceName) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Skip tracing for certain paths
			if shouldSkip(r.URL.Path) {
				next.ServeHTTP(w, r)
				return
			}

			// Extract or generate trace ID
			traceID := r.Header.Get(TraceIDHeader)
			if traceID == "" {
				traceID = GenerateTraceID()
			}

			// Set up trace context
			ctx := WithTraceContext(r.Context(), traceID)
			spanID := GetSpanID(ctx)

			// Build metadata
			metadata := map[string]any{
				"method":      r.Method,
				"path":        r.URL.Path,
				"query":       r.URL.RawQuery,
				"remote_addr": r.RemoteAddr,
				"user_agent":  r.UserAgent(),
			}

			// Build tags
			tags := map[string]string{
				"endpoint": normalizePath(r.URL.Path),
				"method":   r.Method,
			}

			// Publish start event
			publisher.PublishStart(ctx, Operations.HTTPRequestReceived, service, metadata, tags)
			startTime := time.Now()

			// Wrap response writer to capture status
			wrapped := newResponseWriter(w)

			// Add trace headers to response
			wrapped.Header().Set(TraceIDHeader, traceID)
			wrapped.Header().Set(SpanIDHeader, spanID)

			// Process request
			next.ServeHTTP(wrapped, r.WithContext(ctx))

			// Calculate duration
			durationMs := int(time.Since(startTime).Milliseconds())

			// Determine status
			status := StatusSuccess
			var errorMsg string
			if wrapped.statusCode >= 500 {
				status = StatusError
				errorMsg = http.StatusText(wrapped.statusCode)
			}

			// Update metadata and tags
			metadata["status_code"] = wrapped.statusCode
			metadata["duration_ms"] = durationMs
			tags["status_code"] = http.StatusText(wrapped.statusCode)

			// Publish end event
			publisher.PublishEnd(
				ctx,
				Operations.HTTPResponseSent,
				service,
				spanID,
				status,
				durationMs,
				metadata,
				tags,
				errorMsg,
			)
		})
	}
}

// skipPaths are paths that don't need tracing.
var skipPaths = []string{"/health", "/metrics", "/favicon.ico"}

func shouldSkip(path string) bool {
	for _, skip := range skipPaths {
		if strings.HasPrefix(path, skip) {
			return true
		}
	}
	return false
}

// uuidPattern matches UUID-like strings.
var uuidPattern = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

// numericPattern matches numeric IDs.
var numericPattern = regexp.MustCompile(`^\d+$`)

// normalizePath normalizes URL path for consistent tagging.
// /api/users/123 -> /api/users/{id}
// /api/tasks/abc-def-ghi -> /api/tasks/{id}
func normalizePath(path string) string {
	parts := strings.Split(path, "/")
	normalized := make([]string, 0, len(parts))

	for _, part := range parts {
		if part == "" {
			continue
		}
		// UUID-like or numeric ID
		if uuidPattern.MatchString(part) || numericPattern.MatchString(part) || len(part) > 20 {
			normalized = append(normalized, "{id}")
		} else {
			normalized = append(normalized, part)
		}
	}

	if len(normalized) == 0 {
		return "/"
	}
	return "/" + strings.Join(normalized, "/")
}

// InjectTraceHeaders adds trace context to outgoing HTTP request headers.
// Use when making requests to other services.
func InjectTraceHeaders(r *http.Request) *http.Request {
	ctx := r.Context()
	if traceID := GetTraceID(ctx); traceID != "" {
		r.Header.Set(TraceIDHeader, traceID)
	}
	if spanID := GetSpanID(ctx); spanID != "" {
		r.Header.Set(SpanIDHeader, spanID)
	}
	return r
}

// TracedClient wraps http.Client with automatic trace header injection.
type TracedClient struct {
	*http.Client
}

// NewTracedClient creates a new traced HTTP client.
func NewTracedClient(client *http.Client) *TracedClient {
	if client == nil {
		client = http.DefaultClient
	}
	return &TracedClient{client}
}

// Do performs the request with trace headers injected.
func (c *TracedClient) Do(r *http.Request) (*http.Response, error) {
	InjectTraceHeaders(r)
	return c.Client.Do(r)
}
