from __future__ import annotations

from dataclasses import dataclass

from app.knowledge_base.models import AssetRegistryConfig, AssetTypeConfig, KnowledgeBaseConfig


@dataclass(frozen=True)
class EnterpriseAssetRegistry:
    """Query asset type behavior without hardcoding ask routes."""

    config: AssetRegistryConfig

    def list_asset_types(self) -> list[str]:
        """Return all configured asset types."""
        return sorted(self.config.asset_types)

    def list_knowledge_bases(self) -> list[str]:
        """Return all configured knowledge-base storage views."""
        return sorted(self.config.stores)

    def get_asset_type(self, asset_type: str) -> AssetTypeConfig:
        """Return configuration for one asset type or raise if unknown."""
        try:
            return self.config.asset_types[asset_type]
        except KeyError as exc:
            raise KeyError(f"Unknown asset type: {asset_type}") from exc

    def get_knowledge_base(self, name: str) -> KnowledgeBaseConfig:
        """Return configuration for one knowledge-base store/view."""
        try:
            return self.config.stores[name]
        except KeyError as exc:
            raise KeyError(f"Unknown knowledge base: {name}") from exc

    def is_direct_route(self, asset_type: str) -> bool:
        """Return whether an asset type can be selected as a primary route."""
        return self.get_asset_type(asset_type).direct_route is True

    def is_consultable_route(self, asset_type: str) -> bool:
        """Return whether an asset type can answer questions but not execute."""
        return self.get_asset_type(asset_type).direct_route == "consult_only"

    def is_supporting_asset(self, asset_type: str) -> bool:
        """Return whether an asset type only supports other routes."""
        return self.get_asset_type(asset_type).direct_route is False

    def is_executable(self, asset_type: str) -> bool:
        """Return whether assets of this type can be handed to orchestration."""
        return self.get_asset_type(asset_type).executable

    def route_kind_for(self, asset_type: str) -> str:
        return self.get_asset_type(asset_type).route_kind

    def stores_for(self, asset_type: str) -> list[str]:
        """Return the storage views used by one asset type."""
        return list(self.get_asset_type(asset_type).stores)

    def owner_kb_for(self, asset_type: str) -> str | None:
        """Return the logical owner knowledge base for one asset type."""
        return self.get_asset_type(asset_type).owner_kb

    def asset_types_for_store(self, store: str) -> list[str]:
        self.get_knowledge_base(store)
        return sorted(
            asset_type
            for asset_type, config in self.config.asset_types.items()
            if store in config.stores
        )

    def can_use_relation(self, asset_type: str, relation: str) -> bool:
        return relation in self.get_asset_type(asset_type).valid_relations

    def to_dict(self) -> dict:
        return self.config.model_dump(mode="json")
