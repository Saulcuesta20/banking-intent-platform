from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.catalog_store import AssetCatalogStore


@dataclass
class EnterpriseAssetRepository:
    """In-memory catalog of loaded enterprise assets."""

    assets: list[EnterpriseAsset] = field(default_factory=list)
    _assets: dict[str, EnterpriseAsset] = field(init=False)
    _by_type: dict[str, list[EnterpriseAsset]] = field(init=False)

    def __post_init__(self) -> None:
        """Build fast lookup indexes from the provided assets."""
        self._assets = {asset.asset_id: asset for asset in self.assets}
        self._by_type: dict[str, list[EnterpriseAsset]] = defaultdict(list)
        for asset in self._assets.values():
            self._by_type[asset.asset_type].append(asset)

    @classmethod
    def from_catalog_store(cls, store: AssetCatalogStore) -> "EnterpriseAssetRepository":
        """Load approved enterprise assets from the processed asset catalog."""
        store.initialize(clear=False)
        rows = store.list_assets(status="all", limit=10_000)
        return cls([EnterpriseAsset.model_validate(row["payload"]) for row in rows])

    def get(self, asset_id: str) -> EnterpriseAsset | None:
        """Return one asset by id, or None when it is unknown."""
        return self._assets.get(asset_id)

    def list_assets(self, asset_type: str | None = None, approved_only: bool = True) -> list[EnterpriseAsset]:
        """List assets, optionally filtered by type and approval status."""
        assets = self._by_type.get(asset_type, []) if asset_type else list(self._assets.values())
        if approved_only:
            assets = [asset for asset in assets if asset.is_approved]
        return sorted(assets, key=lambda asset: (asset.asset_type, asset.asset_id))

    def find_related(self, asset_id: str, relation_type: str | None = None) -> list[EnterpriseAsset]:
        """Find assets that point to the given asset id through relations."""
        values = []
        for asset in self._assets.values():
            for relation in asset.relations:
                if relation.target_asset_id != asset_id:
                    continue
                if relation_type is not None and relation.type != relation_type:
                    continue
                values.append(asset)
        return sorted(values, key=lambda asset: (asset.asset_type, asset.asset_id))
