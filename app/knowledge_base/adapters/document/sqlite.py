from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SQLiteDocumentKnowledgeBaseAdapter:
    """SQLite document KB for rules, QA, documents, and corpus evidence."""

    path: Path

    def initialize(self, *, clear: bool = False) -> None:
        """Create document tables and optionally remove previous documents."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    collection TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    title TEXT,
                    text TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection, document_id)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_text ON documents(text)")
            if clear:
                connection.execute("DELETE FROM documents")

    def upsert_document(self, collection: str, document_id: str, payload: dict[str, Any]) -> None:
        """Persist one document payload."""
        title = payload.get("name") or payload.get("asset_id") or document_id
        text = " ".join(
            str(payload.get(key) or "")
            for key in ["asset_id", "asset_type", "name", "description", "text"]
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (collection, document_id, title, text, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(collection, document_id) DO UPDATE SET
                    title = excluded.title,
                    text = excluded.text,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (collection, document_id, title, text, json.dumps(payload, ensure_ascii=False)),
            )

    def get_document(self, collection: str, document_id: str) -> dict[str, Any] | None:
        """Load one document payload."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM documents WHERE collection = ? AND document_id = ?",
                (collection, document_id),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def search_documents(self, collection: str | None, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search document payloads with a simple local text filter."""
        where = ["text LIKE ?"]
        params: list[Any] = [f"%{query}%"]
        if collection:
            where.append("collection = ?")
            params.append(collection)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT collection, document_id, title, payload_json
                FROM documents
                WHERE {' AND '.join(where)}
                ORDER BY collection, document_id
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
        return [
            {
                "collection": row["collection"],
                "document_id": row["document_id"],
                "title": row["title"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection
