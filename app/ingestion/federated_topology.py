from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry

_CANONICAL_TOPOLOGY_ASSET_TYPES = {
    "concept": "entity",
    "ontology": "entity",
}


@dataclass(frozen=True)
class FederatedKnowledgeBaseSpec:
    name: str
    vector_collection: str
    document_collection: str
    graph_namespace: str
    asset_types: tuple[str, ...]


@dataclass(frozen=True)
class FederatedMemoryCollections:
    global_asset_index: str
    asset_alias_memory: str
    relation_alias_memory: str
    evidence_memory: str


@dataclass(frozen=True)
class FederatedRoutePlan:
    owner_kb: str
    vector_collection: str
    document_collection: str
    graph_namespace: str
    alias_memory_collection: str
    relation_memory_collection: str


@dataclass
class FederatedKnowledgeTopology:
    memory_collections: FederatedMemoryCollections
    knowledge_bases: dict[str, FederatedKnowledgeBaseSpec]

    @classmethod
    def from_yaml(cls, path: Path) -> "FederatedKnowledgeTopology":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        memory = raw.get("memory_collections") or {}
        memory_collections = FederatedMemoryCollections(
            global_asset_index=str(memory.get("global_asset_index") or "knowledge_assets"),
            asset_alias_memory=str(memory.get("asset_alias_memory") or "asset_alias_memory"),
            relation_alias_memory=str(memory.get("relation_alias_memory") or "relation_alias_memory"),
            evidence_memory=str(memory.get("evidence_memory") or "evidence_memory"),
        )
        knowledge_bases: dict[str, FederatedKnowledgeBaseSpec] = {}
        for kb_name, config in (raw.get("knowledge_bases") or {}).items():
            if not isinstance(config, dict):
                continue
            normalized_asset_types: list[str] = []
            seen_asset_types: set[str] = set()
            for value in config.get("asset_types", []):
                asset_type = _canonical_topology_asset_type(str(value))
                if not asset_type or asset_type in seen_asset_types:
                    continue
                seen_asset_types.add(asset_type)
                normalized_asset_types.append(asset_type)
            knowledge_bases[str(kb_name)] = FederatedKnowledgeBaseSpec(
                name=str(kb_name),
                vector_collection=str(config.get("vector_collection") or f"kb_{kb_name}_assets"),
                document_collection=str(config.get("document_collection") or f"kb_{kb_name}_documents"),
                graph_namespace=str(config.get("graph_namespace") or kb_name),
                asset_types=tuple(normalized_asset_types),
            )
        return cls(memory_collections=memory_collections, knowledge_bases=knowledge_bases)

    def route_asset(self, asset: EnterpriseAsset, registry: EnterpriseAssetRegistry) -> FederatedRoutePlan:
        owner_kb = asset.owner or registry.owner_kb_for(asset.asset_type) or "repository"
        kb = self.knowledge_bases.get(owner_kb)
        if kb is None:
            vector_collection = f"kb_{owner_kb}_assets"
            document_collection = f"kb_{owner_kb}_documents"
            graph_namespace = owner_kb
        else:
            vector_collection = kb.vector_collection
            document_collection = kb.document_collection
            graph_namespace = kb.graph_namespace
        return FederatedRoutePlan(
            owner_kb=owner_kb,
            vector_collection=vector_collection,
            document_collection=document_collection,
            graph_namespace=graph_namespace,
            alias_memory_collection=self.memory_collections.asset_alias_memory,
            relation_memory_collection=self.memory_collections.relation_alias_memory,
        )

    def build_alias_memory_records(self, assets: list[EnterpriseAsset]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for asset in assets:
            payload = asset.payload if isinstance(asset.payload, dict) else {}
            aliases = payload.get("aliases") if isinstance(payload.get("aliases"), list) else []
            for alias in aliases:
                if not isinstance(alias, str) or not alias.strip():
                    continue
                records.append(
                    {
                        "id": f"alias::{asset.asset_id}::{_slug(alias)}",
                        "text": alias,
                        "payload": {
                            "asset_id": asset.asset_id,
                            "asset_type": asset.asset_type,
                            "owner_kb": asset.owner,
                            "canonical_name": asset.name,
                            "alias": alias,
                        },
                    }
                )
        return records

    def build_relation_memory_records(self, assets: list[EnterpriseAsset]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for asset in assets:
            for index, relation in enumerate(asset.relations, start=1):
                metadata = relation.metadata if isinstance(relation.metadata, dict) else {}
                raw_type = str(metadata.get("raw_relation_type") or relation.type)
                records.append(
                    {
                        "id": f"relation::{asset.asset_id}::{index}",
                        "text": raw_type,
                        "payload": {
                            "source_asset_id": asset.asset_id,
                            "source_asset_type": asset.asset_type,
                            "target_asset_id": relation.target_asset_id,
                            "canonical_relation_type": relation.type,
                            "relation_family": metadata.get("relation_family"),
                            "normalization_strategy": metadata.get("normalization_strategy"),
                        },
                    }
                )
        return records

    def build_federated_vector_records(
        self,
        assets: list[EnterpriseAsset],
        registry: EnterpriseAssetRegistry,
    ) -> dict[str, list[dict[str, Any]]]:
        collections: dict[str, list[dict[str, Any]]] = {
            self.memory_collections.global_asset_index: [],
        }
        for asset in assets:
            route = self.route_asset(asset, registry)
            collections.setdefault(route.vector_collection, [])
            text = _asset_text(asset)
            payload = {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "owner_kb": route.owner_kb,
                "graph_namespace": route.graph_namespace,
                "name": asset.name,
            }
            record = {"id": asset.asset_id, "text": text, "payload": payload}
            collections[self.memory_collections.global_asset_index].append(record)
            collections[route.vector_collection].append(record)
        return collections


def _asset_text(asset: EnterpriseAsset) -> str:
    parts = [asset.name or "", asset.description or "", asset.text or ""]
    payload = asset.payload if isinstance(asset.payload, dict) else {}
    definition = payload.get("definition")
    if definition:
        parts.append(str(definition))
    return "\n".join(part for part in parts if part).strip() or asset.asset_id


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def _canonical_topology_asset_type(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    return _CANONICAL_TOPOLOGY_ASSET_TYPES.get(normalized, normalized)
