from __future__ import annotations

from app.audit.providers import AuditSink


class NoopAuditSink(AuditSink):
    """Audit sink used when audit persistence is intentionally disabled."""

    def record(self, event: dict[str, object]) -> None:
        """Accept an event without storing or emitting it."""
        return None
