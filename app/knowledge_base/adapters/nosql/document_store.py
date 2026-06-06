from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryDocumentKnowledgeBaseAdapter:
    """NoSQL-style document adapter used as a local/test baseline."""

    _collections: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def upsert_document(self, collection: str, document_id: str, payload: dict[str, Any]) -> None:
        self._collections.setdefault(collection, {})[document_id] = deepcopy(payload)

    def get_document(self, collection: str, document_id: str) -> dict[str, Any] | None:
        document = self._collections.get(collection, {}).get(document_id)
        return deepcopy(document) if document is not None else None
