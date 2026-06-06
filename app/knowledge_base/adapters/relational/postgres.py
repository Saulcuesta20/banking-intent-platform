from __future__ import annotations

from typing import Any


class PostgresKnowledgeBaseRelationalAdapter:
    """Relational adapter placeholder for runtime state, audit, and monitoring."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def record_runtime_event(self, event_type: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError("Postgres runtime-event persistence is not wired yet.")
