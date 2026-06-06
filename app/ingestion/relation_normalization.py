from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.knowledge_base.models import AssetRelation
from app.knowledge_base.ports import VectorKnowledgeBaseAdapter


@dataclass(frozen=True)
class RelationDefinition:
    canonical_type: str
    family: str
    aliases: tuple[str, ...] = ()
    source_asset_types: tuple[str, ...] = ()
    target_asset_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationNormalizationResult:
    canonical_type: str
    family: str
    strategy: str
    valid: bool
    review_required: bool


@dataclass
class RelationRegistry:
    definitions: dict[str, RelationDefinition]
    alias_index: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "RelationRegistry":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        relation_rows = raw.get("relations") or {}
        definitions: dict[str, RelationDefinition] = {}
        alias_index: dict[str, str] = {}
        for canonical_type, config in relation_rows.items():
            if not isinstance(config, dict):
                continue
            definition = RelationDefinition(
                canonical_type=str(canonical_type),
                family=str(config.get("family") or "semantic"),
                aliases=tuple(str(alias).strip() for alias in config.get("aliases", []) if str(alias).strip()),
                source_asset_types=tuple(str(value) for value in config.get("source_asset_types", []) if str(value).strip()),
                target_asset_types=tuple(str(value) for value in config.get("target_asset_types", []) if str(value).strip()),
            )
            definitions[definition.canonical_type] = definition
            alias_index[_normalize_relation_text(definition.canonical_type)] = definition.canonical_type
            for alias in definition.aliases:
                alias_index[_normalize_relation_text(alias)] = definition.canonical_type
        return cls(definitions=definitions, alias_index=alias_index)

    def resolve(self, raw_type: str) -> RelationDefinition | None:
        canonical = self.alias_index.get(_normalize_relation_text(raw_type))
        if canonical is None:
            return None
        return self.definitions.get(canonical)


@dataclass
class RelationNormalizationService:
    registry: RelationRegistry
    vector_memory: VectorKnowledgeBaseAdapter | None = None
    memory_collection: str = "relation_alias_memory"
    vector_similarity_threshold: float = 0.82

    def seed_vector_memory(self) -> None:
        if self.vector_memory is None:
            return
        records: list[dict[str, Any]] = []
        for definition in self.registry.definitions.values():
            for alias in {definition.canonical_type, *definition.aliases}:
                records.append(
                    {
                        "id": f"relation::{definition.canonical_type}::{_normalize_relation_text(alias)}",
                        "text": alias,
                        "payload": {
                            "canonical_relation_type": definition.canonical_type,
                            "relation_family": definition.family,
                            "alias": alias,
                            "source_asset_types": list(definition.source_asset_types),
                            "target_asset_types": list(definition.target_asset_types),
                        },
                    }
                )
        self.vector_memory.upsert_texts(self.memory_collection, records)

    def normalize_relation(
        self,
        relation: AssetRelation,
        *,
        source_asset_type: str,
        target_asset_type: str | None = None,
    ) -> AssetRelation:
        raw_type = relation.type
        definition = self.registry.resolve(raw_type)
        strategy = "registry_alias"
        if definition is None and self.vector_memory is not None:
            definition = self._resolve_from_vector_memory(raw_type)
            strategy = "vector_similarity" if definition is not None else "fallback_raw"
        if definition is None:
            metadata = {
                **relation.metadata,
                "raw_relation_type": raw_type,
                "canonical_relation_type": raw_type,
                "relation_family": relation.metadata.get("relation_family", "unknown"),
                "normalization_strategy": strategy,
                "review_required": True,
            }
            return AssetRelation(type=raw_type, target_asset_id=relation.target_asset_id, metadata=metadata)

        valid = self._is_valid(definition, source_asset_type=source_asset_type, target_asset_type=target_asset_type)
        review_required = not valid or strategy == "vector_similarity"
        metadata = {
            **relation.metadata,
            "raw_relation_type": raw_type,
            "canonical_relation_type": definition.canonical_type,
            "relation_family": definition.family,
            "normalization_strategy": strategy,
            "review_required": review_required,
            "valid_for_asset_types": valid,
        }
        return AssetRelation(type=definition.canonical_type, target_asset_id=relation.target_asset_id, metadata=metadata)

    def normalize_relation_type(
        self,
        raw_relation_type: str,
        *,
        source_asset_type: str,
        target_asset_type: str | None = None,
    ) -> RelationNormalizationResult:
        definition = self.registry.resolve(raw_relation_type)
        strategy = "registry_alias"
        if definition is None and self.vector_memory is not None:
            definition = self._resolve_from_vector_memory(raw_relation_type)
            strategy = "vector_similarity" if definition is not None else "fallback_raw"
        if definition is None:
            return RelationNormalizationResult(
                canonical_type=raw_relation_type,
                family="unknown",
                strategy=strategy,
                valid=False,
                review_required=True,
            )
        valid = self._is_valid(definition, source_asset_type=source_asset_type, target_asset_type=target_asset_type)
        return RelationNormalizationResult(
            canonical_type=definition.canonical_type,
            family=definition.family,
            strategy=strategy,
            valid=valid,
            review_required=(not valid or strategy == "vector_similarity"),
        )

    def _resolve_from_vector_memory(self, raw_type: str) -> RelationDefinition | None:
        if self.vector_memory is None:
            return None
        results = self.vector_memory.search_texts(self.memory_collection, raw_type, limit=3)
        for result in results:
            score = float(result.get("score") or 0.0)
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
            canonical = str(payload.get("canonical_relation_type") or "").strip()
            if score >= self.vector_similarity_threshold and canonical in self.registry.definitions:
                return self.registry.definitions[canonical]
        return None

    @staticmethod
    def _is_valid(
        definition: RelationDefinition,
        *,
        source_asset_type: str,
        target_asset_type: str | None,
    ) -> bool:
        if definition.source_asset_types and source_asset_type not in definition.source_asset_types:
            return False
        if target_asset_type and definition.target_asset_types and target_asset_type not in definition.target_asset_types:
            return False
        return True


def _normalize_relation_text(value: str) -> str:
    return " ".join(str(value).casefold().replace("_", " ").replace(".", " ").split())
