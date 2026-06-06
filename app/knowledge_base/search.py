from __future__ import annotations

import re
from dataclasses import dataclass

from app.knowledge_base.models import AssetSearchResult, EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.knowledge_base.repository import EnterpriseAssetRepository


@dataclass(frozen=True)
class AssetSearchService:
    """Search approved enterprise assets without binding ask to one storage engine."""

    registry: EnterpriseAssetRegistry
    repository: EnterpriseAssetRepository

    def search(
        self,
        query: str,
        *,
        asset_types: list[str] | None = None,
        limit: int = 10,
    ) -> AssetSearchResult:
        """Search approved assets and group them as primary, supporting, or evidence."""
        tokens = self._tokens(query)
        matches = [
            asset
            for asset in self.repository.list_assets(approved_only=True)
            if asset_types is None or asset.asset_type in asset_types
        ]
        ranked = sorted(
            ((self._score(asset, tokens), asset) for asset in matches),
            key=lambda item: (-item[0], item[1].asset_type, item[1].asset_id),
        )
        selected = [asset for score, asset in ranked if score > 0][:limit]

        primary: list[EnterpriseAsset] = []
        supporting: list[EnterpriseAsset] = []
        evidence: list[EnterpriseAsset] = []
        for asset in selected:
            try:
                if self.registry.is_direct_route(asset.asset_type):
                    primary.append(asset)
                elif self.registry.is_consultable_route(asset.asset_type):
                    supporting.append(asset)
                else:
                    evidence.append(asset)
            except KeyError:
                # Graph-published launcher metadata is useful evidence, but it is
                # not itself an Ask route unless the registry declares it.
                evidence.append(asset)

        return AssetSearchResult(
            query=query,
            primary_assets=primary,
            supporting_assets=supporting,
            evidence_assets=evidence,
        )

    def related_assets(self, asset_id: str) -> list[EnterpriseAsset]:
        """Return approved assets directly referenced by the given asset."""
        asset = self.repository.get(asset_id)
        if asset is None:
            return []
        related = [
            self.repository.get(target_id)
            for target_id in asset.relation_targets()
        ]
        return [item for item in related if item is not None and item.is_approved]

    @staticmethod
    def _tokens(query: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9_áéíóúñÁÉÍÓÚÑ]+", query.lower())
            if len(token) > 2
        }

    @staticmethod
    def _score(asset: EnterpriseAsset, tokens: set[str]) -> int:
        if not tokens:
            return 0
        searchable = " ".join(
            [
                asset.asset_id,
                asset.asset_type,
                asset.name or "",
                asset.description,
                asset.text,
                " ".join(asset.tags),
                str(asset.payload.get("canonical_name") or "") if isinstance(asset.payload, dict) else "",
                " ".join(str(value) for value in (asset.payload.get("aliases") or [])) if isinstance(asset.payload, dict) else "",
            ]
        ).lower()
        return sum(1 for token in tokens if token in searchable)
