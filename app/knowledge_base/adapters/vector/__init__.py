"""Vector database adapters for the knowledge base."""

from app.knowledge_base.adapters.vector.qdrant import QdrantKnowledgeBaseVectorAdapter

__all__ = ["QdrantKnowledgeBaseVectorAdapter"]
