"""Tests for A2ATracer - A2A Protocol tracing for agent-to-agent communication."""

import pytest

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


def test_correlation_id_parameter():
    """Test that correlation_id is properly logged when provided."""
    tracer = A2ATracer()
    correlation_id = "corr-abc-123"
    tracer.log_a2a_message(
        direction="request",
        from_="duq-core",
        to="agent",
        message="Test message",
        task_id="task-001",
        correlation_id=correlation_id,
    )
    logs = tracer.get_recent_logs(limit=1)
    assert logs[0]["correlation_id"] == correlation_id


def test_deque_overflow_behavior():
    """Test that old logs are dropped when max_logs limit is exceeded."""
    tracer = A2ATracer(max_logs=3)
    # Add 5 messages to exceed the limit of 3
    for i in range(5):
        tracer.log_a2a_message(
            direction="request",
            from_="duq-core",
            to="agent",
            message=f"Message {i}",
            task_id=f"task-{i}",
        )
    # Should only have the last 3 messages
    all_logs = tracer.get_recent_logs(limit=100)
    assert len(all_logs) == 3
    # Most recent should be task-4 (reversed order)
    assert all_logs[0]["task_id"] == "task-4"
    assert all_logs[1]["task_id"] == "task-3"
    assert all_logs[2]["task_id"] == "task-2"
    # task-0 and task-1 should be dropped
    task_ids = [log["task_id"] for log in all_logs]
    assert "task-0" not in task_ids
    assert "task-1" not in task_ids


def test_dialogue_chronological_order():
    """Test that get_task_dialogue returns logs in chronological order."""
    tracer = A2ATracer()
    task_id = "task-order-test"
    # Add multiple messages for the same task
    for i in range(3):
        tracer.log_a2a_message(
            direction="request" if i % 2 == 0 else "response",
            from_="duq-core" if i % 2 == 0 else "agent",
            to="agent" if i % 2 == 0 else "duq-core",
            message=f"Message {i}",
            task_id=task_id,
        )
    dialogue = tracer.get_task_dialogue(task_id)
    assert len(dialogue) == 3
    # Should be in chronological order (not reversed like get_recent_logs)
    assert "Message 0" in dialogue[0]["message_preview"]
    assert "Message 1" in dialogue[1]["message_preview"]
    assert "Message 2" in dialogue[2]["message_preview"]


def test_empty_input_validation():
    """Test that ValueError is raised for empty task_id, from_, or to."""
    tracer = A2ATracer()

    # Test empty task_id
    with pytest.raises(ValueError, match="task_id, from_, and to must be non-empty strings"):
        tracer.log_a2a_message(
            direction="request",
            from_="duq-core",
            to="agent",
            message="Test",
            task_id="",
        )

    # Test empty from_
    with pytest.raises(ValueError, match="task_id, from_, and to must be non-empty strings"):
        tracer.log_a2a_message(
            direction="request",
            from_="",
            to="agent",
            message="Test",
            task_id="task-123",
        )

    # Test empty to
    with pytest.raises(ValueError, match="task_id, from_, and to must be non-empty strings"):
        tracer.log_a2a_message(
            direction="request",
            from_="duq-core",
            to="",
            message="Test",
            task_id="task-123",
        )


def test_nonexistent_task_query():
    """Test that get_task_dialogue returns empty list for nonexistent task_id."""
    tracer = A2ATracer()
    # Add some logs for different tasks
    tracer.log_a2a_message(
        direction="request",
        from_="duq-core",
        to="agent",
        message="Test",
        task_id="task-exists",
    )
    # Query for a task that doesn't exist
    dialogue = tracer.get_task_dialogue("nonexistent-task")
    assert dialogue == []
