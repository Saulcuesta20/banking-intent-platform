from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.knowledge_base.repository import EnterpriseAssetRepository


@dataclass(frozen=True)
class AssetSyncResult:
    output_path: Path
    assets_written: int
    graph_assets: int
    vector_assets: int
    repository_assets: int

    def to_dict(self) -> dict:
        return {
            "output_path": str(self.output_path),
            "assets_written": self.assets_written,
            "graph_assets": self.graph_assets,
            "vector_assets": self.vector_assets,
            "repository_assets": self.repository_assets,
        }


@dataclass(frozen=True)
class AssetSyncService:
    """Write a neutral asset index that graph/vector loaders can consume."""

    repository: EnterpriseAssetRepository
    output_directory: Path

    def sync(self) -> AssetSyncResult:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        assets = self.repository.list_assets(approved_only=True)
        payload = {
            "assets": [asset.model_dump(mode="json") for asset in assets],
            "graph": [
                self._graph_payload(asset)
                for asset in assets
                if asset.relations
            ],
            "vector": [
                self._vector_payload(asset)
                for asset in assets
                if asset.text or asset.description
            ],
        }
        output_path = self.output_directory / "enterprise_assets.index.json"
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return AssetSyncResult(
            output_path=output_path,
            assets_written=len(assets),
            graph_assets=len(payload["graph"]),
            vector_assets=len(payload["vector"]),
            repository_assets=len(assets),
        )

    @staticmethod
    def _graph_payload(asset) -> dict:
        return {
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "name": asset.name,
            "relations": [relation.model_dump(mode="json") for relation in asset.relations],
        }

    @staticmethod
    def _vector_payload(asset) -> dict:
        return {
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "text": "\n".join(value for value in [asset.name or "", asset.description, asset.text] if value),
            "tags": asset.tags,
            "source_refs": asset.source_refs,
        }
