from __future__ import annotations

from app.models import KnowledgeRecord
from app.knowledge_graph.providers import KnowledgeGraphRepository


class KnowledgeGraphService:
    """Application boundary for searching and updating approved knowledge."""

    def __init__(self, repository: KnowledgeGraphRepository):
        self.repository = repository

    def search(self, search_terms: list[str]) -> list[KnowledgeRecord]:
        return self.repository.search(search_terms)

    def upsert_record(self, record: KnowledgeRecord) -> None:
        self.repository.upsert_record(record)

    def ingest(self, records: list[KnowledgeRecord]) -> None:
        self.repository.initialize()
        for record in records:
            self.repository.upsert_record(record)
