from __future__ import annotations

from typing import Any, Protocol

from app.models import KnowledgeRecord


class KnowledgeBaseSearchPort(Protocol):
    def search(self, search_terms: list[str]) -> list[KnowledgeRecord]:
        """Return approved knowledge candidates matching understood terms."""


class KnowledgeBaseWritePort(Protocol):
    def initialize(self) -> None:
        """Create storage constraints required by the adapter."""

    def upsert_record(self, record: KnowledgeRecord) -> None:
        """Persist an approved flow record in the adapter."""


class KnowledgeBaseRepository(KnowledgeBaseSearchPort, KnowledgeBaseWritePort, Protocol):
    """Combined read/write repository used by current ingestion and ask flows."""


class GraphKnowledgeBaseAdapter(KnowledgeBaseRepository, Protocol):
    """Adapter contract for graph databases such as Neo4j."""


class VectorKnowledgeBaseAdapter(Protocol):
    """Adapter contract for vector databases such as Qdrant."""

    def upsert_texts(self, collection: str, records: list[dict[str, Any]]) -> None:
        """Index text records for semantic retrieval."""

    def search_texts(self, collection: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return semantically similar records."""


class NoSQLKnowledgeBaseAdapter(Protocol):
    """Adapter contract for document stores such as MongoDB."""

    def upsert_document(self, collection: str, document_id: str, payload: dict[str, Any]) -> None:
        """Persist one document payload."""

    def get_document(self, collection: str, document_id: str) -> dict[str, Any] | None:
        """Load one document payload."""


class RelationalKnowledgeBaseAdapter(Protocol):
    """Adapter contract for RDBMS stores such as Postgres."""

    def record_runtime_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Persist runtime/audit state in a relational store."""
