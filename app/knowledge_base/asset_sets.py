from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.adapters.document.sqlite import SQLiteDocumentKnowledgeBaseAdapter
from app.knowledge_base.adapters.graph.neo4j import Neo4jKnowledgeBaseGraphAdapter
from app.knowledge_base.adapters.vector.qdrant import QdrantKnowledgeBaseVectorAdapter
from app.knowledge_base.models import AssetRelation, EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.models import KnowledgeRecord, Task


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
        assets = [
            self._load_asset(entry, manifest=manifest, manifest_path=manifest_path)
            for entry in manifest.spec.assets
        ]
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
        return self.store.transition_asset_set(
            asset_set_id=manifest.metadata.id,
            version=manifest.metadata.version,
            to_status="ready_for_review",
            actor=actor,
            comment=comment,
        )

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
        source_path = Path(str((asset_set.get("metadata") or {}).get("source_path") or ""))
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
                comment=f"Asset {asset_id} edited in Lowdefy Asset Studio.",
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
        return {
            "valid": True,
            "asset_id": normalized["asset_id"],
            "asset_type": asset_type,
            "relation_count": len(relations),
            "stores": list(config.stores),
            "validators": list(config.validators),
        }

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
        vector_records: list[dict[str, Any]] = []
        for member in asset_set.get("members") or []:
            asset = EnterpriseAsset.model_validate(member["payload"]).model_copy(
                update={"status": "active"}
            )
            stores = set(member.get("stores") or [])
            if "graph" in stores:
                if self.graph is None:
                    raise RuntimeError("Graph projection is required but no graph adapter is configured")
                self.graph.upsert_asset(asset)
                if asset.asset_type == "flow":
                    body = asset.payload
                    flow_id = str(body.get("flow_id") or asset.asset_id.removeprefix("flow."))
                    task_names = [str(value) for value in body.get("user_tasks") or []]
                    self.graph.upsert_record(
                        KnowledgeRecord(
                            flow_id=flow_id,
                            flow_name=str(body.get("flow_name") or asset.name or flow_id),
                            intent=str(body.get("intent") or asset.description),
                            confidence=1,
                            business_event=str(body.get("business_event") or "unknown"),
                            utterances=[str(body.get("intent") or asset.description)],
                            plan=task_names,
                            tasks=[Task(task=name, type="user_task") for name in task_names],
                            user_tasks=[],
                            capabilities=[],
                            concepts=[],
                            explanation=asset.description,
                            source=f"asset_set:{asset_set['asset_set_id']}@{asset_set['version']}",
                            metadata={
                                "asset_id": asset.asset_id,
                                "asset_set_id": asset_set["asset_set_id"],
                                "asset_set_version": asset_set["version"],
                                "catalog_status": "active",
                            },
                        )
                    )
                self._increment_projection(results, "graph")
            if "document" in stores:
                if self.document is None:
                    raise RuntimeError("Document projection is required but no document adapter is configured")
                self.document.upsert_document(asset.asset_type, asset.asset_id, asset.model_dump(mode="json"))
                self._increment_projection(results, "document")
            if "vector" in stores:
                if self.vector is None:
                    raise RuntimeError("Vector projection is required but no vector adapter is configured")
                vector_records.append(
                    {
                        "id": f"{asset.asset_id}:{asset.version}",
                        "text": "\n".join(
                            value for value in [asset.name or "", asset.description, asset.text] if value
                        ),
                        "payload": asset.model_dump(mode="json"),
                    }
                )
            for store in stores & {"repository", "relational"}:
                self._increment_projection(results, store)
        if vector_records:
            self.vector.upsert_texts("enterprise_assets_active", vector_records)
            results["vector"] = {"status": "completed", "asset_count": len(vector_records)}
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
        asset_id = str(document.get("asset_id") or document.get("assetId") or "").strip()
        if not asset_id:
            raise ValueError(f"Asset in {source_ref} must define asset_id")
        payload = dict(document.get("payload") or {})
        payload.setdefault("domain_id", manifest.metadata.domain)
        payload.setdefault("module_id", manifest.metadata.module)
        payload["asset_set_id"] = manifest.metadata.id
        payload["asset_set_version"] = manifest.metadata.version
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
        return normalized

    @staticmethod
    def _asset_set_root(directory: Path) -> Path:
        if directory.parent.name == "versions":
            return directory.parent.parent
        return directory

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
