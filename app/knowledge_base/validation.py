from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge_base.models import EnterpriseAsset
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.knowledge_base.repository import EnterpriseAssetRepository


@dataclass(frozen=True)
class AssetValidationIssue:
    asset_id: str
    severity: str
    message: str


@dataclass(frozen=True)
class AssetValidationResult:
    valid: bool
    checked_assets: int
    issues: list[AssetValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "checked_assets": self.checked_assets,
            "issues": [issue.__dict__ for issue in self.issues],
        }


@dataclass(frozen=True)
class AssetValidationService:
    registry: EnterpriseAssetRegistry
    repository: EnterpriseAssetRepository

    def validate(self) -> AssetValidationResult:
        assets = self.repository.list_assets(approved_only=False)
        known_ids = {asset.asset_id for asset in assets}
        issues: list[AssetValidationIssue] = []
        for asset in assets:
            issues.extend(self._validate_asset(asset, known_ids))
        return AssetValidationResult(
            valid=not any(issue.severity == "error" for issue in issues),
            checked_assets=len(assets),
            issues=issues,
        )

    def _validate_asset(self, asset: EnterpriseAsset, known_ids: set[str]) -> list[AssetValidationIssue]:
        issues: list[AssetValidationIssue] = []
        try:
            self.registry.get_asset_type(asset.asset_type)
        except KeyError:
            issues.append(
                AssetValidationIssue(asset.asset_id, "error", f"Unknown asset_type: {asset.asset_type}")
            )
            return issues

        if not asset.name:
            issues.append(AssetValidationIssue(asset.asset_id, "warning", "Asset has no display name."))
        for relation in asset.relations:
            if not self.registry.can_use_relation(asset.asset_type, relation.type):
                issues.append(
                    AssetValidationIssue(
                        asset.asset_id,
                        "error",
                        f"Relation {relation.type} is not valid for asset_type {asset.asset_type}.",
                    )
                )
            if relation.target_asset_id not in known_ids and asset.asset_type not in {"flow", "process"}:
                issues.append(
                    AssetValidationIssue(
                        asset.asset_id,
                        "warning",
                        f"Relation target is not present in repository: {relation.target_asset_id}",
                    )
                )
        return issues
