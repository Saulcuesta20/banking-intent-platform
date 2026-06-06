from __future__ import annotations

from dataclasses import dataclass

from app.ask.providers import FlowSelectionProvider
from app.models import KnowledgeRecord


@dataclass(frozen=True)
class FlowSelectionService:
    """Select an existing flow that answers an understood customer question."""

    provider: FlowSelectionProvider

    def select(self, question: str, records: list[KnowledgeRecord]) -> KnowledgeRecord | None:
        return self.provider.select_intent(question, records)
