from __future__ import annotations

from app.intent.providers import SemanticReasoningProvider
from app.models import KnowledgeRecord


class LocalSemanticReasoningProvider(SemanticReasoningProvider):
    def classify_intent(
        self, question: str, records: list[KnowledgeRecord]
    ) -> KnowledgeRecord | None:
        if records:
            return records[0]
        return None
