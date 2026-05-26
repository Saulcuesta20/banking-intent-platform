from __future__ import annotations

from app.ask.providers import FlowSelectionProvider
from app.models import KnowledgeRecord


class FlowSelectionService:
    """Select an existing flow that answers an understood customer question."""

    def __init__(self, provider: FlowSelectionProvider):
        self.provider = provider

    def select(self, question: str, records: list[KnowledgeRecord]) -> KnowledgeRecord | None:
        return self.provider.select_intent(question, records)
