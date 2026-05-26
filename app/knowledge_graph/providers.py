from __future__ import annotations

from typing import Protocol

from app.models import KnowledgeRecord


class KnowledgeGraphRepository(Protocol):
    def initialize(self) -> None:
        """Create storage constraints required by the knowledge graph."""

    def upsert_record(self, record: KnowledgeRecord) -> None:
        """Persist a flow record as graph nodes and relationships."""

    def search(self, search_terms: list[str]) -> list[KnowledgeRecord]:
        """Return graph-backed flow candidates matching understood terms."""
