from __future__ import annotations

from typing import Protocol

from app.models import KnowledgeRecord


class GraphRepository(Protocol):
    def upsert_record(self, record: KnowledgeRecord) -> None:
        """Persist a flow record as graph nodes and relationships."""

    def find_related(self, intent: str) -> dict[str, list[str]]:
        """Return graph neighbors for an intent."""
