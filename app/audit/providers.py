from __future__ import annotations

from typing import Protocol


class AuditSink(Protocol):
    """Port for components that persist or emit audit events."""

    def record(self, event: dict[str, object]) -> None:
        """Persist or emit an audit event."""
