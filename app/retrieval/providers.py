from __future__ import annotations

from typing import Protocol

from app.models import KnowledgeRecord


class KnowledgeRetrievalProvider(Protocol):
    def retrieve(self, question: str) -> list[KnowledgeRecord]:
        """Return flow records relevant to a question."""
