"""Governed enterprise knowledge base component."""

from app.knowledge_base.models import EnterpriseAsset, EvidenceBundle, KnowledgeEvidence, KnowledgeSourceRoute
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.search import AssetSearchService
from app.knowledge_base.service import KnowledgeBaseService
from app.knowledge_base.source_router import KnowledgeSourceRouter

__all__ = [
    "AssetSearchService",
    "EnterpriseAsset",
    "EnterpriseAssetRegistry",
    "EnterpriseAssetRepository",
    "EvidenceBundle",
    "KnowledgeEvidence",
    "KnowledgeBaseService",
    "KnowledgeSourceRoute",
    "KnowledgeSourceRouter",
]
