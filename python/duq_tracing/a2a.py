"""A2A Protocol tracing for agent-to-agent communication.

Example logging configuration:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Enable A2A tracing logs
    logging.getLogger("duq.a2a").setLevel(logging.INFO)
"""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

logger = logging.getLogger(__name__)

SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9._\-+=\/]{10,}"), "[REDACTED:API_KEY]"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9._\-+=\/]+"), "Bearer [REDACTED]"),
    (re.compile(r"token[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9._\-+=\/]{10,}"), "token: [REDACTED]"),
]

MAX_PREVIEW_LENGTH = 500


@dataclass
class A2ALogEntry:
    """Structured log entry for A2A communication."""

    type: str = "a2a_message"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    task_id: str = ""
    direction: Literal["request", "response"] = "request"
    from_: str = ""
    to: str = ""
    message_preview: str = ""
    correlation_id: str | None = None
    requires_approval: bool = False
    approval_context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with 'from' key instead of 'from_'."""
        result = asdict(self)
        result["from"] = result.pop("from_")
        return result


class A2ATracer:
    """Tracer for A2A protocol messages between duq-core and agents."""

    def __init__(self, max_logs: int = 1000) -> None:
        """Initialize tracer with bounded log storage.

        Args:
            max_logs: Maximum number of logs to retain in memory.
        """
        self._logs: deque[dict[str, Any]] = deque(maxlen=max_logs)
        self._logger = logging.getLogger("duq.a2a")

    def _mask_secrets(self, text: str) -> str:
        """Mask sensitive data in text."""
        result = text
        for pattern, replacement in SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    def _truncate(self, text: str, max_length: int = MAX_PREVIEW_LENGTH) -> str:
        """Truncate text with ellipsis if exceeds max length."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def log_a2a_message(
        self,
        direction: Literal["request", "response"],
        from_: str,
        to: str,
        message: str,
        task_id: str,
        requires_approval: bool = False,
        approval_context: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Log an A2A protocol message.

        Args:
            direction: Message direction ('request' or 'response').
            from_: Source agent/service identifier.
            to: Destination agent/service identifier.
            message: Full message content.
            task_id: Task identifier for correlation.
            requires_approval: Whether this message requires human approval.
            approval_context: Context for approval decision (risk level, description).
            correlation_id: Optional correlation ID for request-response matching.

        Raises:
            ValueError: If task_id, from_, or to are empty or None.
        """
        if not task_id or not from_ or not to:
            raise ValueError("task_id, from_, and to must be non-empty strings")

        masked = self._mask_secrets(message)
        preview = self._truncate(masked)

        entry = A2ALogEntry(
            task_id=task_id,
            direction=direction,
            from_=from_,
            to=to,
            message_preview=preview,
            correlation_id=correlation_id,
            requires_approval=requires_approval,
            approval_context=approval_context,
        )

        log_dict = entry.to_dict()
        self._logs.append(log_dict)
        self._logger.info(json.dumps(log_dict))

    def get_recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent logs in reverse chronological order.

        Args:
            limit: Maximum number of logs to return.

        Returns:
            List of log entries, most recent first.
        """
        logs = list(self._logs)
        logs.reverse()
        return logs[:limit]

    def get_task_dialogue(self, task_id: str) -> list[dict[str, Any]]:
        """Get all logs for a specific task.

        Args:
            task_id: Task identifier to filter by.

        Returns:
            List of log entries for the task in chronological order.
        """
        return [log for log in self._logs if log["task_id"] == task_id]
