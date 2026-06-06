from __future__ import annotations

import hashlib
import math
from typing import Any


class QdrantKnowledgeBaseVectorAdapter:
    """Qdrant vector adapter for semantic knowledge-base indexes."""

    def __init__(self, host: str, api_key: str | None = None, vector_size: int = 64):
        self.host = host
        self.api_key = api_key
        self.vector_size = vector_size
        self.client = self._build_client()

    def upsert_texts(self, collection: str, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        self._ensure_collection(collection)
        models = self._models()
        points = []
        for record in records:
            record_id = str(record["id"])
            text = str(record.get("text") or "")
            payload = dict(record.get("payload") or {})
            payload.setdefault("text", text)
            points.append(
                models.PointStruct(
                    id=self._point_id(record_id),
                    vector=self._embed(text),
                    payload=payload,
                )
            )
        self.client.upsert(collection_name=collection, points=points)

    def search_texts(self, collection: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        limit = int(limit)
        vector = self._embed(query)
        try:
            if hasattr(self.client, "search"):
                results = self.client.search(collection_name=collection, query_vector=vector, limit=limit)
            else:
                results = self.client.query_points(
                    collection_name=collection,
                    query=vector,
                    limit=limit,
                    with_payload=True,
                ).points
        except Exception as exc:
            raise RuntimeError(f"Could not search Qdrant collection {collection!r}.") from exc
        return [
            {
                "score": item.score,
                "payload": item.payload,
            }
            for item in results
        ]

    def clear_collection(self, collection: str) -> None:
        try:
            self.client.delete_collection(collection_name=collection)
        except Exception:
            return

    def _build_client(self):
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError("qdrant-client is required for vector knowledge-base indexing.") from exc
        return QdrantClient(url=self.host, api_key=self.api_key)

    def _ensure_collection(self, collection: str) -> None:
        models = self._models()
        collections = self.client.get_collections().collections
        if any(item.name == collection for item in collections):
            return
        self.client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=self.vector_size, distance=models.Distance.COSINE),
        )

    @staticmethod
    def _models():
        from qdrant_client import models

        return models

    @staticmethod
    def _point_id(value: str) -> str:
        digest = hashlib.md5(value.encode("utf-8")).hexdigest()
        return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.vector_size
        tokens = [token for token in text.lower().split() if token]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.vector_size
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
