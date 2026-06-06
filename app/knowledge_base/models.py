from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


KnowledgeBaseType = Literal["repository", "graph", "vector", "document", "relational"]
KnowledgeViewType = Literal["repository", "graph", "vector", "document", "relational", "external_api"]
KnowledgeSourceType = Literal[
    "qa",
    "rules_policies",
    "process_flows",
    "entities",
    "configurations",
    "tools_apis",
]
DirectRouteMode = bool | Literal["consult_only"]


class KnowledgeBaseConfig(BaseModel):
    role: str
    description: str = ""

    model_config = {"frozen": True}


class AssetTypeConfig(BaseModel):
    description: str = ""
    owner_kb: str | None = None
    direct_route: DirectRouteMode = False
    route_kind: str = "supporting_knowledge"
    executable: bool = False
    execution_target: str | None = None
    stores: list[KnowledgeBaseType] = Field(default_factory=list)
    valid_relations: list[str] = Field(default_factory=list)
    validators: list[str] = Field(default_factory=list)
    runtime_usage: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _validate_execution_target(self) -> "AssetTypeConfig":
        if self.executable and not self.execution_target:
            raise ValueError("executable asset types must define execution_target")
        return self


class AssetRegistryConfig(BaseModel):
    version: str = "1.0.0"
    description: str = ""
    stores: dict[str, KnowledgeBaseConfig] = Field(default_factory=dict)
    asset_types: dict[str, AssetTypeConfig] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def _validate_store_references(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        stores = set((data.get("stores") or {}).keys())
        asset_types = data.get("asset_types") or {}
        for asset_type, config in asset_types.items():
            if not isinstance(config, dict):
                continue
            unknown = [store for store in config.get("stores", []) if store not in stores]
            if unknown:
                raise ValueError(
                    f"asset type {asset_type} references unknown knowledge stores: {', '.join(unknown)}"
                )
        return data


class AssetRelation(BaseModel):
    type: str
    target_asset_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class AssetEvidence(BaseModel):
    source_ref: str
    quote: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class KnowledgeSourceRoute(BaseModel):
    source: KnowledgeSourceType
    reason: str
    views: list[KnowledgeViewType] = Field(default_factory=list)
    asset_types: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class KnowledgeEvidence(BaseModel):
    evidence_id: str
    source: KnowledgeSourceType
    view: KnowledgeViewType
    asset_id: str
    asset_type: str
    title: str = ""
    snippet: str = ""
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class EvidenceBundle(BaseModel):
    question: str
    routes: list[KnowledgeSourceRoute] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)

    model_config = {"frozen": True}

    def to_trace_payload(self) -> dict[str, Any]:
        return {
            "routes": [
                {
                    "source": route.source,
                    "views": route.views,
                    "asset_types": route.asset_types,
                    "reason": route.reason,
                }
                for route in self.routes
            ],
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "source": item.source,
                    "view": item.view,
                    "asset_id": item.asset_id,
                    "asset_type": item.asset_type,
                    "title": item.title,
                    "confidence": item.confidence,
                }
                for item in self.evidence
            ],
        }


class EnterpriseAsset(BaseModel):
    asset_id: str
    asset_type: str
    name: str | None = None
    version: str = "1.0.0"
    status: Literal[
        "candidate",
        "draft",
        "ready_for_review",
        "in_review",
        "validated",
        "active",
        "approved",
        "deprecated",
        "retired",
        "rejected",
    ] = "approved"
    owner: str | None = None
    description: str = ""
    text: str = ""
    tags: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    relations: list[AssetRelation] = Field(default_factory=list)
    evidence: list[AssetEvidence] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @property
    def is_approved(self) -> bool:
        return self.status in {"approved", "validated", "active"}

    def relation_targets(self, relation_type: str | None = None) -> list[str]:
        return [
            relation.target_asset_id
            for relation in self.relations
            if relation_type is None or relation.type == relation_type
        ]


class AssetSearchResult(BaseModel):
    query: str = ""
    primary_assets: list[EnterpriseAsset] = Field(default_factory=list)
    supporting_assets: list[EnterpriseAsset] = Field(default_factory=list)
    evidence_assets: list[EnterpriseAsset] = Field(default_factory=list)

    model_config = {"frozen": True}

    def all_assets(self) -> list[EnterpriseAsset]:
        return [*self.primary_assets, *self.supporting_assets, *self.evidence_assets]
