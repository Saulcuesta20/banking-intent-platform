from __future__ import annotations

from dataclasses import dataclass

from app.audit.providers import AuditSink
from app.models import AnswerResult


@dataclass(frozen=True)
class AuditService:
    """Application service that writes audit events for ask outcomes."""

    sink: AuditSink

    def record_intent_result(self, question: str, result: AnswerResult) -> None:
        """Record the selected flow, intent, confidence, and approval flag."""
        self.sink.record(
            {
                "event_type": "intent_resolved",
                "question": question,
                "flow_id": result.flow_id,
                "intent": result.intent,
                "confidence": result.confidence,
                "business_event": result.business_event,
                "requires_human_approval": result.requires_human_approval,
            }
        )
