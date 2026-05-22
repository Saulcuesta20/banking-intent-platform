from __future__ import annotations

from app.models import KnowledgeRecord
from app.retrieval.providers import KnowledgeRetrievalProvider


class KnowledgeRetrievalService:
    def __init__(self, provider: KnowledgeRetrievalProvider):
        self.provider = provider

    def retrieve(self, question: str) -> list[KnowledgeRecord]:
        return self.provider.retrieve(question)
