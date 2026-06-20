from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from app.config.asset_contracts import AssetContractRegistry
from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.adapters.document.sqlite import SQLiteDocumentKnowledgeBaseAdapter
from app.knowledge_base.adapters.graph.neo4j import Neo4jKnowledgeBaseGraphAdapter
from app.knowledge_base.adapters.vector.qdrant import QdrantKnowledgeBaseVectorAdapter
from app.knowledge_base.models import AssetRelation, EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.config.settings import load_settings

from app.ingestion.federated_topology import FederatedKnowledgeTopology


class AssetSetMetadata(BaseModel):
    id: str
    name: str
    version: str
    domain: str | None = None
    module: str | None = None
    description: str = ""
    git_commit: str | None = None
    tags: list[str] = Field(default_factory=list)


class AssetSetSpec(BaseModel):
    asset_type: str = Field(alias="assetType")
    assets: list[str | dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class AssetSetManifest(BaseModel):
    api_version: str = Field(alias="apiVersion")
    kind: str
    metadata: AssetSetMetadata
    spec: AssetSetSpec

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_kind(self) -> "AssetSetManifest":
        if self.kind != "AssetSet":
            raise ValueError("kind must be AssetSet")
        if not self.spec.assets:
            raise ValueError("AssetSet must contain at least one asset")
        return self


@dataclass(frozen=True)
class AssetSetDeploymentService:
    store: AssetCatalogStore
    registry: EnterpriseAssetRegistry
    graph: Neo4jKnowledgeBaseGraphAdapter | None = None
    vector: QdrantKnowledgeBaseVectorAdapter | None = None
    document: SQLiteDocumentKnowledgeBaseAdapter | None = None
    contract_registry: AssetContractRegistry | None = None

    def load(
        self,
        manifest_path: Path,
        *,
        actor: str = "ingestion",
        comment: str = "Technical validation completed.",
    ) -> dict[str, Any]:
        """Validate and register an AssetSet YAML version as ready for human review."""
        manifest_path = manifest_path.resolve()
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest = AssetSetManifest.model_validate(raw)
        assets: list = []
        skipped: list = []
        for entry in manifest.spec.assets:
            try:
                assets.append(
                    self._load_asset(entry, manifest=manifest, manifest_path=manifest_path)
                )
            except Exception as exc:
                skipped.append({"asset": str(entry), "error": str(exc)})
        if not assets and skipped:
            raise ValueError(
                f"All {len(skipped)} assets failed validation in {manifest.metadata.id}: "
                + "; ".join(s["error"] for s in skipped[:3])
            )
        canonical = {
            "manifest": manifest.model_dump(mode="json", by_alias=True),
            "assets": [asset.model_dump(mode="json") for asset in assets],
        }
        checksum = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        existing = self.store.get_asset_set(manifest.metadata.id, manifest.metadata.version)
        if existing is not None:
            if existing["checksum"] == checksum:
                return existing
            raise ValueError(
                f"AssetSet version is immutable: {manifest.metadata.id}@{manifest.metadata.version}. "
                "Create a new version for changed content."
            )
        for asset in assets:
            self.store.upsert_asset(asset, self.registry)
        self.store.upsert_asset_set(
            asset_set_id=manifest.metadata.id,
            name=manifest.metadata.name,
            version=manifest.metadata.version,
            status="draft",
            checksum=checksum,
            domain_id=manifest.metadata.domain,
            module_id=manifest.metadata.module,
            asset_type=manifest.spec.asset_type,
            description=manifest.metadata.description,
            git_commit=manifest.metadata.git_commit,
            metadata={
                "tags": manifest.metadata.tags,
                "source_path": str(manifest_path),
                "api_version": manifest.api_version,
            },
            members=[(asset.asset_id, asset.version) for asset in assets],
        )
        return {
            **self.store.transition_asset_set(
                asset_set_id=manifest.metadata.id,
                version=manifest.metadata.version,
                to_status="ready_for_review",
                actor=actor,
                comment=comment,
            ),
            "skipped_assets": skipped,
        }

    def load_directory(self, root: Path) -> list[dict[str, Any]]:
        """Load every asset-set.yaml below a directory."""
        manifests = sorted(root.rglob("asset-set.yaml"))
        return [self.load(path) for path in manifests]

    def create_draft_version(
        self,
        *,
        asset_id: str,
        base_version: str | None,
        document: dict[str, Any],
        actor: str,
        new_version: str | None = None,
    ) -> dict[str, Any]:
        """Create an immutable AssetSet version containing an edited asset."""
        catalog_asset = self.store.get_catalog_asset(asset_id, base_version)
        if catalog_asset is None:
            raise KeyError(f"Catalog asset not found: {asset_id}@{base_version or 'latest'}")
        asset_set_id = catalog_asset.get("asset_set_id")
        asset_set_version = catalog_asset.get("asset_set_version")
        if not asset_set_id or not asset_set_version:
            raise ValueError(f"Asset is not managed by an AssetSet: {asset_id}")
        asset_set = self.store.get_asset_set(str(asset_set_id), str(asset_set_version))
        if asset_set is None:
            raise KeyError(f"AssetSet version not found: {asset_set_id}@{asset_set_version}")
        source_path = self._canonical_manifest_path(
            Path(str((asset_set.get("metadata") or {}).get("source_path") or ""))
        )
        if not source_path.is_file():
            raise ValueError(f"AssetSet source manifest is unavailable: {source_path}")

        manifest_raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        manifest = AssetSetManifest.model_validate(manifest_raw)
        target_version = new_version or self._next_version(manifest.metadata.version)
        if self.store.get_asset_set(manifest.metadata.id, target_version) is not None:
            raise ValueError(
                f"AssetSet version already exists: {manifest.metadata.id}@{target_version}"
            )

        asset_set_root = self._asset_set_root(source_path.parent)
        version_directory = asset_set_root / "versions" / target_version
        if version_directory.exists():
            raise ValueError(f"AssetSet source version already exists: {version_directory}")
        version_directory.mkdir(parents=True)

        edited = False
        copied_entries: list[str | dict[str, Any]] = []
        try:
            for entry in manifest.spec.assets:
                if isinstance(entry, dict):
                    asset_document = dict(entry)
                    relative_path = f"assets/{self._asset_filename(asset_document)}"
                else:
                    source_asset_path = (source_path.parent / entry).resolve()
                    asset_document = yaml.safe_load(source_asset_path.read_text(encoding="utf-8"))
                    relative_path = str(entry)
                current_id = str(
                    asset_document.get("asset_id") or asset_document.get("assetId") or ""
                )
                if current_id == asset_id:
                    asset_document = self._normalize_editor_document(
                        document,
                        expected_asset_id=asset_id,
                        expected_asset_type=manifest.spec.asset_type,
                    )
                    edited = True
                asset_document["version"] = target_version
                target_path = version_directory / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(
                    yaml.safe_dump(asset_document, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                copied_entries.append(relative_path)
            if not edited:
                raise ValueError(f"Asset {asset_id} is not a member of {manifest.metadata.id}")

            manifest_raw["metadata"]["version"] = target_version
            manifest_raw["metadata"]["git_commit"] = None
            manifest_raw["spec"]["assets"] = copied_entries
            target_manifest = version_directory / "asset-set.yaml"
            target_manifest.write_text(
                yaml.safe_dump(manifest_raw, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            loaded = self.load(
                target_manifest,
                actor=actor,
                comment=f"Asset {asset_id} edited in launcher asset editor.",
            )
            return {
                **loaded,
                "edited_asset_id": asset_id,
                "created_by": actor,
                "source_path": str(target_manifest),
            }
        except Exception:
            shutil.rmtree(version_directory, ignore_errors=True)
            raise

    def preview_draft_version(
        self,
        *,
        asset_id: str,
        base_version: str | None,
        document: dict[str, Any],
        environment: str = "dev",
        new_version: str | None = None,
    ) -> dict[str, Any]:
        catalog_asset = self.store.get_catalog_asset(asset_id, base_version)
        if catalog_asset is None:
            raise KeyError(f"Catalog asset not found: {asset_id}@{base_version or 'latest'}")
        asset_set_id = catalog_asset.get("asset_set_id")
        asset_set_version = catalog_asset.get("asset_set_version")
        if not asset_set_id or not asset_set_version:
            raise ValueError(f"Asset is not managed by an AssetSet: {asset_id}")
        asset_set = self.store.get_asset_set(str(asset_set_id), str(asset_set_version))
        if asset_set is None:
            raise KeyError(f"AssetSet version not found: {asset_set_id}@{asset_set_version}")
        target_version = new_version or self._next_version(str(asset_set_version))
        normalized = self._normalize_editor_document(
            document,
            expected_asset_id=asset_id,
            expected_asset_type=str(catalog_asset["asset_type"]),
        )
        before = self._catalog_asset_document(catalog_asset)
        after = {
            **normalized,
            "version": target_version,
            "payload": {
                **dict(normalized.get("payload") or {}),
                "asset_set_id": str(asset_set_id),
                "asset_set_version": target_version,
            },
        }
        validation = self.validate_asset_document(
            document=normalized,
            expected_asset_id=asset_id,
            expected_asset_type=str(catalog_asset["asset_type"]),
        )
        projection_preview = self.projection_preview_for_document(
            document=after,
            environment=environment,
        )
        changed = self._diff_documents(before, after)
        return {
            "asset_id": asset_id,
            "asset_type": catalog_asset["asset_type"],
            "asset_set_id": asset_set_id,
            "base_version": asset_set_version,
            "draft_version": target_version,
            "environment": environment,
            "validation": validation,
            "diff": changed,
            "projection_preview": projection_preview,
            "deployment_impact": {
                "active_version_remains": catalog_asset.get("active_environment") or environment,
                "message": (
                    f"Ask and runtime projections keep using {asset_set_id}@{asset_set_version} "
                    f"until {asset_set_id}@{target_version} is reviewed, validated, and deployed."
                ),
            },
        }

    def diff_asset_versions(
        self,
        *,
        asset_id: str,
        from_version: str,
        to_version: str,
    ) -> dict[str, Any]:
        before_asset = self.store.get_catalog_asset(asset_id, from_version)
        after_asset = self.store.get_catalog_asset(asset_id, to_version)
        if before_asset is None:
            raise KeyError(f"Catalog asset not found: {asset_id}@{from_version}")
        if after_asset is None:
            raise KeyError(f"Catalog asset not found: {asset_id}@{to_version}")
        before = self._catalog_asset_document(before_asset)
        after = self._catalog_asset_document(after_asset)
        return {
            "asset_id": asset_id,
            "from_version": from_version,
            "to_version": to_version,
            "diff": self._diff_documents(before, after),
        }

    def projection_preview(
        self,
        *,
        asset_id: str,
        version: str | None,
        environment: str = "dev",
    ) -> dict[str, Any]:
        catalog_asset = self.store.get_catalog_asset(asset_id, version)
        if catalog_asset is None:
            raise KeyError(f"Catalog asset not found: {asset_id}@{version or 'latest'}")
        return {
            "asset_id": asset_id,
            "version": catalog_asset["version"],
            "environment": environment,
            "projection_preview": self.projection_preview_for_document(
                document=self._catalog_asset_document(catalog_asset),
                environment=environment,
            ),
        }

    def projection_preview_for_document(
        self,
        *,
        document: dict[str, Any],
        environment: str = "dev",
    ) -> dict[str, Any]:
        asset_type = str(document["asset_type"])
        config = self.registry.get_asset_type(asset_type)
        payload = dict(document.get("payload") or {})
        semantic_text = "\n".join(
            str(value)
            for value in [
                document.get("name") or "",
                document.get("description") or "",
                document.get("text") or "",
                payload.get("intent") or "",
                payload.get("business_event") or "",
            ]
            if value
        )
        relation_count = len(document.get("relations") or [])
        stores: dict[str, dict[str, Any]] = {}
        for store in config.stores:
            if store == "graph":
                detail = f"{relation_count} relationships staged"
            elif store == "vector":
                detail = "semantic text changed" if semantic_text else "metadata-only projection"
            elif store == "document":
                detail = "document index pending"
            elif store == "repository":
                detail = "YAML pending commit"
            elif store == "relational":
                detail = "catalog rows pending version insert"
            else:
                detail = "projection pending"
            stores[store] = {
                "status": "staging",
                "environment": environment,
                "detail": detail,
                "asset_count": 1,
            }
        return {
            "stores": stores,
            "required_stores": list(config.stores),
            "relation_count": relation_count,
            "semantic_text_length": len(semantic_text),
        }

    def validate_asset_document(
        self,
        *,
        document: dict[str, Any],
        expected_asset_id: str | None = None,
        expected_asset_type: str | None = None,
    ) -> dict[str, Any]:
        normalized = self._normalize_editor_document(
            document,
            expected_asset_id=expected_asset_id,
            expected_asset_type=expected_asset_type,
        )
        asset_type = str(normalized["asset_type"])
        config = self.registry.get_asset_type(asset_type)
        relations = normalized.get("relations") or []
        contract_validation = self._contracts().validate_document(normalized)
        return {
            "valid": True,
            "asset_id": normalized["asset_id"],
            "asset_type": asset_type,
            "relation_count": len(relations),
            "stores": list(config.stores),
            "validators": list(config.validators),
            "contract_validation": contract_validation.to_dict(),
            "warnings": contract_validation.warnings,
        }

    @staticmethod
    def _catalog_asset_document(asset: dict[str, Any]) -> dict[str, Any]:
        stored = dict(asset.get("payload") or {})
        if stored.get("asset_id"):
            document = stored
        else:
            document = {
                "asset_id": asset["asset_id"],
                "asset_type": asset["asset_type"],
                "name": asset.get("name"),
                "version": asset.get("version"),
                "tags": asset.get("tags") or [],
                "relations": asset.get("relationships") or [],
                "payload": asset.get("payload") or {},
            }
        document = dict(document)
        document.setdefault("asset_id", asset["asset_id"])
        document.setdefault("asset_type", asset["asset_type"])
        document.setdefault("name", asset.get("name") or asset["asset_id"])
        document.setdefault("version", asset.get("version"))
        document.setdefault("tags", asset.get("tags") or [])
        document.setdefault("relations", asset.get("relationships") or [])
        document.setdefault("payload", asset.get("payload") or {})
        return document

    @classmethod
    def _diff_documents(cls, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        fields = ["asset_id", "asset_type", "name", "description", "version", "text"]
        field_changes = [
            {"field": field, "before": before.get(field), "after": after.get(field)}
            for field in fields
            if before.get(field) != after.get(field)
        ]
        payload_changes = cls._mapping_changes(
            before.get("payload") if isinstance(before.get("payload"), Mapping) else {},
            after.get("payload") if isinstance(after.get("payload"), Mapping) else {},
        )
        before_tags = [str(tag) for tag in before.get("tags") or []]
        after_tags = [str(tag) for tag in after.get("tags") or []]
        before_relations = cls._relation_keys(before.get("relations") or [])
        after_relations = cls._relation_keys(after.get("relations") or [])
        return {
            "changed": bool(
                field_changes
                or payload_changes
                or before_tags != after_tags
                or before_relations != after_relations
            ),
            "fields": field_changes,
            "payload": payload_changes,
            "tags": {
                "added": sorted(set(after_tags) - set(before_tags)),
                "removed": sorted(set(before_tags) - set(after_tags)),
                "unchanged": sorted(set(before_tags) & set(after_tags)),
            },
            "relations": {
                "added": sorted(after_relations - before_relations),
                "removed": sorted(before_relations - after_relations),
                "unchanged": sorted(before_relations & after_relations),
            },
            "summary": cls._diff_summary(field_changes, payload_changes, before_relations, after_relations),
        }

    @staticmethod
    def _mapping_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
        keys = sorted(set(before) | set(after))
        return [
            {"field": key, "before": before.get(key), "after": after.get(key)}
            for key in keys
            if before.get(key) != after.get(key)
        ]

    @staticmethod
    def _relation_keys(relations: list[Any]) -> set[str]:
        keys = set()
        for relation in relations:
            if isinstance(relation, Mapping):
                relation_type = relation.get("type") or relation.get("relation_type")
                target = relation.get("target_asset_id") or relation.get("targetAssetId")
                if relation_type and target:
                    keys.add(f"{relation_type}->{target}")
        return keys

    @staticmethod
    def _diff_summary(
        fields: list[dict[str, Any]],
        payload: list[dict[str, Any]],
        before_relations: set[str],
        after_relations: set[str],
    ) -> list[str]:
        values = []
        if fields:
            values.append(f"{len(fields)} top-level fields changed")
        if payload:
            values.append(f"{len(payload)} payload fields changed")
        added_relations = len(after_relations - before_relations)
        removed_relations = len(before_relations - after_relations)
        if added_relations or removed_relations:
            values.append(f"{added_relations} relationships added, {removed_relations} removed")
        return values or ["No structural changes detected"]

    def deploy(
        self,
        *,
        asset_set_id: str,
        version: str,
        environment: str,
        actor: str,
    ) -> dict[str, Any]:
        """Project a validated AssetSet and atomically activate it in the catalog."""
        asset_set = self.store.get_asset_set(asset_set_id, version)
        if asset_set is None:
            raise KeyError(f"AssetSet version not found: {asset_set_id}@{version}")
        if asset_set["status"] not in {"validated", "active"}:
            raise ValueError("Only a validated AssetSet version can be deployed")
        projection_results = self._project(asset_set)
        return self.store.deploy_asset_set(
            asset_set_id=asset_set_id,
            version=version,
            environment=environment,
            actor=actor,
            projection_results=projection_results,
        )

    def _project(self, asset_set: dict[str, Any]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        vector_records_by_collection: dict[str, list[dict[str, Any]]] = {}
        settings = load_settings()
        topology = FederatedKnowledgeTopology.from_yaml(settings.federated_topology_path)
        kb_to_collection = {kb_name: spec.vector_collection for kb_name, spec in topology.knowledge_bases.items()}
        for member in asset_set.get("members") or []:
            asset = EnterpriseAsset.model_validate(member["payload"]).model_copy(
                update={"status": "active"}
            )
            stores = set(member.get("stores") or [])
            if "graph" in stores:
                if self.graph is None:
                    raise RuntimeError("Graph projection is required but no graph adapter is configured")
                self.graph.upsert_asset(asset)
                self._increment_projection(results, "graph")
            if "document" in stores:
                if self.document is None:
                    raise RuntimeError("Document projection is required but no document adapter is configured")
                self.document.upsert_document(asset.asset_type, asset.asset_id, asset.model_dump(mode="json"))
                self._increment_projection(results, "document")
            if "vector" in stores:
                if self.vector is None:
                    raise RuntimeError("Vector projection is required but no vector adapter is configured")
                owner_kb = self.registry.owner_kb_for(asset.asset_type) or "enterprise_assets_active"
                collection = kb_to_collection.get(owner_kb, "enterprise_assets_active")
                vector_records_by_collection.setdefault(collection, []).append(
                    {
                        "id": asset.asset_id,
                        "text": "\n".join(
                            value for value in [asset.name or "", asset.description, asset.text] if value
                        ),
                        "payload": asset.model_dump(mode="json"),
                    }
                )
            for store in stores & {"repository", "relational"}:
                self._increment_projection(results, store)
        for collection, records in vector_records_by_collection.items():
            self.vector.upsert_texts(collection, records)
            results["vector"] = {"status": "completed", "asset_count": len(records)}
        return results

    @staticmethod
    def _increment_projection(results: dict[str, Any], store: str) -> None:
        current = results.setdefault(store, {"status": "completed", "asset_count": 0})
        current["asset_count"] += 1

    def _load_asset(
        self,
        entry: str | dict[str, Any],
        *,
        manifest: AssetSetManifest,
        manifest_path: Path,
    ) -> EnterpriseAsset:
        source_ref = str(manifest_path)
        if isinstance(entry, str):
            asset_path = (manifest_path.parent / entry).resolve()
            document = yaml.safe_load(asset_path.read_text(encoding="utf-8"))
            source_ref = str(asset_path)
        else:
            document = dict(entry)
        asset_type = str(document.get("asset_type") or document.get("assetType") or manifest.spec.asset_type)
        if asset_type != manifest.spec.asset_type:
            raise ValueError(
                f"Asset {document.get('asset_id') or document.get('assetId')} has type {asset_type}; "
                f"expected {manifest.spec.asset_type}"
            )
        self.registry.get_asset_type(asset_type)
        payload = dict(document.get("payload") or {})
        payload.setdefault("domain_id", manifest.metadata.domain)
        payload.setdefault("module_id", manifest.metadata.module)
        if asset_type == "tool":
            payload.setdefault("tool_type", "backend")
            payload.setdefault("operation", document.get("description") or "")
        payload["asset_set_id"] = manifest.metadata.id
        payload["asset_set_version"] = manifest.metadata.version
        document["payload"] = payload
        document = self._normalize_editor_document(
            document,
            expected_asset_id=None,
            expected_asset_type=manifest.spec.asset_type,
        )
        asset_id = str(document.get("asset_id") or document.get("assetId") or "").strip()
        if not asset_id:
            raise ValueError(f"Asset in {source_ref} must define asset_id")
        relations = [
            AssetRelation(
                type=str(item["type"]),
                target_asset_id=str(item.get("target_asset_id") or item.get("targetAssetId")),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in document.get("relations") or []
        ]
        return EnterpriseAsset(
            asset_id=asset_id,
            asset_type=asset_type,
            name=document.get("name"),
            version=str(document.get("version") or manifest.metadata.version),
            status="draft",
            owner=document.get("owner"),
            description=str(document.get("description") or ""),
            text=str(document.get("text") or ""),
            tags=list(
                dict.fromkeys(
                    [
                        *manifest.metadata.tags,
                        *[str(tag) for tag in document.get("tags") or []],
                    ]
                )
            ),
            source_refs=[source_ref],
            relations=relations,
            payload=payload,
        )

    def _normalize_editor_document(
        self,
        document: dict[str, Any],
        *,
        expected_asset_id: str | None,
        expected_asset_type: str | None,
    ) -> dict[str, Any]:
        if not isinstance(document, dict):
            raise ValueError("Asset document must be an object")
        normalized = dict(document)
        asset_id = str(normalized.get("asset_id") or normalized.get("assetId") or "").strip()
        asset_type = str(
            normalized.get("asset_type") or normalized.get("assetType") or ""
        ).strip()
        if not asset_id:
            raise ValueError("Asset document must define asset_id")
        if not asset_type:
            raise ValueError("Asset document must define asset_type")
        if expected_asset_id and asset_id != expected_asset_id:
            raise ValueError(f"asset_id cannot change: expected {expected_asset_id}")
        if expected_asset_type and asset_type != expected_asset_type:
            raise ValueError(f"asset_type cannot change: expected {expected_asset_type}")
        self.registry.get_asset_type(asset_type)
        normalized["asset_id"] = asset_id
        normalized["asset_type"] = asset_type
        normalized.pop("assetId", None)
        normalized.pop("assetType", None)
        normalized.setdefault("name", asset_id)
        normalized.setdefault("description", "")
        normalized.setdefault("tags", [])
        normalized.setdefault("relations", [])
        normalized.setdefault("payload", {})
        if not isinstance(normalized["payload"], dict):
            raise ValueError("Asset payload must be an object")
        if not isinstance(normalized["tags"], list):
            raise ValueError("Asset tags must be an array")
        if not isinstance(normalized["relations"], list):
            raise ValueError("Asset relations must be an array")
        for relation in normalized["relations"]:
            if not isinstance(relation, dict) or not relation.get("type"):
                raise ValueError("Every relation must define type")
            if not (relation.get("target_asset_id") or relation.get("targetAssetId")):
                raise ValueError("Every relation must define target_asset_id")
        self._contracts().validate_document_or_raise(normalized)
        return normalized

    def _validate_loaded_asset_document(
        self,
        document: dict[str, Any],
        *,
        known_asset_ids: set[str],
    ) -> dict[str, Any]:
        normalized = self._normalize_editor_document(
            document,
            expected_asset_id=None,
            expected_asset_type=None,
        )
        self._contracts().validate_document_or_raise(
            normalized,
            known_asset_ids=known_asset_ids,
            require_known_targets=False,
        )
        return normalized

    def _contracts(self) -> AssetContractRegistry:
        return self.contract_registry or AssetContractRegistry(registry=self.registry)

    @staticmethod
    def _asset_set_root(directory: Path) -> Path:
        if directory.parent.name == "versions":
            return directory.parent.parent
        return directory

    @staticmethod
    def _canonical_manifest_path(source_path: Path) -> Path:
        """Prefer app/assets as the governed YAML root while old catalog rows migrate."""
        if source_path.is_file():
            parts = source_path.parts
            marker = ("app", "launcher", "modules")
            for index in range(0, len(parts) - len(marker) + 1):
                if parts[index:index + len(marker)] == marker:
                    relative = Path(*parts[index + len(marker):])
                    candidate = load_settings().asset_source_path / relative
                    if candidate.is_file():
                        return candidate
                    break
        return source_path

    @staticmethod
    def _asset_filename(document: dict[str, Any]) -> str:
        asset_id = str(document.get("asset_id") or document.get("assetId") or "asset")
        safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in asset_id)
        return f"{safe}.yaml"

    @staticmethod
    def _next_version(version: str) -> str:
        value = version.lstrip("v")
        parts = value.split(".")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            major, minor, patch = (int(part) for part in parts)
            return f"{major}.{minor}.{patch + 1}"
        if value.isdigit():
            return f"{int(value) + 1}.0.0"
        raise ValueError(f"Cannot automatically increment version: {version}")


__all__ = [
    "AssetSetDeploymentService",
    "AssetSetManifest",
]
