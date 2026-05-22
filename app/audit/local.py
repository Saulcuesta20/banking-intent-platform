from __future__ import annotations

from app.audit.providers import AuditSink


class NoopAuditSink(AuditSink):
    def record(self, event: dict[str, object]) -> None:
        return None
