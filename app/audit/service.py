from __future__ import annotations

from app.audit.providers import AuditSink
from app.models import IntentResult


class AuditService:
    def __init__(self, sink: AuditSink):
        self.sink = sink

    def record_intent_result(self, question: str, result: IntentResult) -> None:
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
