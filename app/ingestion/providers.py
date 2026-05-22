from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.models import KnowledgeRecord


class KnowledgeIngestionProvider(Protocol):
    def ingest(self, source: Path) -> list[KnowledgeRecord]:
        """Load flow records from a source path."""
