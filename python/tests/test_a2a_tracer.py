"""Tests for A2ATracer - A2A Protocol tracing for agent-to-agent communication."""

from duq_tracing.a2a import A2ATracer


def test_log_a2a_message_request():
    """Test logging a basic A2A request message."""
    tracer = A2ATracer()
    tracer.log_a2a_message(
        direction="request",
        from_="duq-core",
        to="weather-agent",
        message="What is the weather in Moscow?",
        task_id="task-123",
    )
    logs = tracer.get_recent_logs(limit=1)
    assert len(logs) == 1
    assert logs[0]["direction"] == "request"
    assert logs[0]["from"] == "duq-core"
    assert logs[0]["to"] == "weather-agent"
    assert logs[0]["task_id"] == "task-123"
    assert "timestamp" in logs[0]


def test_log_a2a_message_response_with_approval():
    """Test logging a response that requires approval."""
    tracer = A2ATracer()
    tracer.log_a2a_message(
        direction="response",
        from_="coder-agent",
        to="duq-core",
        message="",
        task_id="task-456",
        requires_approval=True,
        approval_context={
            "description": "Push to master",
            "risk_level": "destructive_irreversible",
        },
    )
    logs = tracer.get_recent_logs(limit=1)
    assert logs[0]["requires_approval"] is True
    assert logs[0]["approval_context"]["risk_level"] == "destructive_irreversible"


def test_message_truncation():
    """Test that long messages are truncated with ellipsis."""
    tracer = A2ATracer()
    long_message = "x" * 1000
    tracer.log_a2a_message(
        direction="request",
        from_="duq-core",
        to="agent",
        message=long_message,
        task_id="task-789",
    )
    logs = tracer.get_recent_logs(limit=1)
    assert len(logs[0]["message_preview"]) <= 500
    assert logs[0]["message_preview"].endswith("...")


def test_secret_masking():
    """Test that secrets are masked in message preview."""
    tracer = A2ATracer()
    tracer.log_a2a_message(
        direction="request",
        from_="duq-core",
        to="agent",
        message="Use token sk-1234567890abcdef and Bearer eyJhbG...",
        task_id="task-mask",
    )
    logs = tracer.get_recent_logs(limit=1)
    assert "sk-1234567890abcdef" not in logs[0]["message_preview"]
    assert "[REDACTED]" in logs[0]["message_preview"]
