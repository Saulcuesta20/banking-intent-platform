from __future__ import annotations

from typing import Protocol

from app.models import KnowledgeRecord


class SemanticReasoningProvider(Protocol):
    def classify_intent(
        self, question: str, records: list[KnowledgeRecord]
    ) -> KnowledgeRecord | None:
        """Classify a question into the best matching flow record."""
