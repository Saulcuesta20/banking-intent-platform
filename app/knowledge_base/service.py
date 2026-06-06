from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import KnowledgeRecord
from app.knowledge_base.models import EvidenceBundle, KnowledgeEvidence, KnowledgeSourceRoute
from app.knowledge_base.ports import KnowledgeBaseRepository
from app.knowledge_base.search import AssetSearchService
from app.knowledge_base.source_router import KnowledgeSourceRouter


@dataclass
class KnowledgeBaseService:
    """Application boundary for searching and updating approved knowledge."""

    repository: KnowledgeBaseRepository
    source_router: KnowledgeSourceRouter = field(default_factory=KnowledgeSourceRouter)

    def search(self, search_terms: list[str]) -> list[KnowledgeRecord]:
        """Search flow/process knowledge records using expanded terms."""
        return self.repository.search(search_terms)

    def upsert_record(self, record: KnowledgeRecord) -> None:
        """Store or update one approved knowledge record."""
        self.repository.upsert_record(record)

    def ingest(self, records: list[KnowledgeRecord], *, clear: bool = False) -> None:
        """Initialize the repository and write all provided records."""
        self.repository.initialize()
        if clear and hasattr(self.repository, "clear"):
            self.repository.clear()
        for record in records:
            self.repository.upsert_record(record)

    def build_evidence_bundle(
        self,
        *,
        question: str,
        search_terms: list[str],
        records: list[KnowledgeRecord],
        question_understanding: dict[str, Any] | None = None,
        asset_search: dict[str, Any] | None = None,
    ) -> EvidenceBundle:
        """Build traceable retrieval evidence from source routes and records."""
        routes = self.source_router.route(
            question=question,
            search_terms=search_terms,
            question_understanding=question_understanding,
            asset_search=asset_search,
        )
        if records and not any(route.source == "process_flows" for route in routes):
            routes.append(
                KnowledgeSourceRoute(
                    source="process_flows",
                    views=["graph", "repository"],
                    asset_types=["flow", "process", "plan"],
                    reason="Knowledge base search returned flow/process candidates.",
                )
            )
        evidence: list[KnowledgeEvidence] = []
        for index, record in enumerate(records, start=1):
            evidence.append(
                KnowledgeEvidence(
                    evidence_id=f"record_{index}",
                    source="process_flows",
                    view="graph",
                    asset_id=record.flow_id,
                    asset_type="flow",
                    title=record.flow_name,
                    snippet=record.explanation,
                    confidence=record.confidence,
                    metadata={
                        "intent": record.intent,
                        "business_event": record.business_event,
                        "source": record.source,
                    },
                )
            )
        evidence.extend(self._asset_search_evidence(asset_search, start=len(evidence) + 1))
        return EvidenceBundle(question=question, routes=routes, evidence=evidence)

    @staticmethod
    def _asset_search_evidence(asset_search: dict[str, Any] | None, *, start: int) -> list[KnowledgeEvidence]:
        if not asset_search or not asset_search.get("enabled"):
            return []
        evidence: list[KnowledgeEvidence] = []
        groups = [
            ("primary_assets", "qa", "repository"),
            ("supporting_assets", "rules_policies", "repository"),
            ("evidence_assets", "process_flows", "repository"),
        ]
        index = start
        for group_key, source, view in groups:
            for asset_id in asset_search.get(group_key, []):
                asset_type = str(asset_id).split(".", 1)[0] if "." in str(asset_id) else "asset"
                evidence.append(
                    KnowledgeEvidence(
                        evidence_id=f"asset_{index}",
                        source=source,
                        view=view,
                        asset_id=str(asset_id),
                        asset_type=asset_type,
                        title=str(asset_id),
                        metadata={"asset_search_group": group_key},
                    )
                )
                index += 1
        return evidence

__all__ = ["AssetSearchService", "KnowledgeBaseService"]
