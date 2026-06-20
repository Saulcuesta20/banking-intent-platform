from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config.model import load_asset_contracts
from app.knowledge_base.registry import EnterpriseAssetRegistry


LEGACY_FIELD_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "flow": {
        "purpose": ("intent", "description", "text"),
        "user_task_refs": ("user_tasks", "tasks"),
        "explanation": ("description", "text"),
        "flow_id": ("transaction_id", "normalized_name"),
        "flow_name": ("canonical_name", "name"),
        "business_event": ("purpose",),
    },
    "module": {
        "purpose": ("description", "label"),
        "name": ("label",),
    },
    "menu": {
        "label": ("name",),
    },
    "form": {
        "purpose": ("description",),
    },
    "process": {
        "name": ("process_name",),
    },
    "business_rule": {
        "name": ("rule_id", "rule_text"),
    },
    "qa": {
        "answer": ("explanation", "description", "text"),
    },
    "tool": {
        "tool_type": ("type", "kind"),
        "operation": ("description", "text"),
    },
}


@dataclass(frozen=True)
class AssetContractValidationResult:
    valid: bool
    asset_type: str
    missing_required_fields: list[str] = field(default_factory=list)
    unsupported_payload_fields: list[str] = field(default_factory=list)
    invalid_relations: list[dict[str, str]] = field(default_factory=list)
    unresolved_relation_targets: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "asset_type": self.asset_type,
            "missing_required_fields": self.missing_required_fields,
            "unsupported_payload_fields": self.unsupported_payload_fields,
            "invalid_relations": self.invalid_relations,
            "unresolved_relation_targets": self.unresolved_relation_targets,
            "warnings": self.warnings,
        }


class AssetContractRegistry:
    """Validate governed asset YAML documents against configured contracts."""

    def __init__(
        self,
        *,
        contracts: dict[str, dict[str, Any]] | None = None,
        registry: EnterpriseAssetRegistry | None = None,
    ):
        self.contracts = contracts or load_asset_contracts()
        self.registry = registry

    def payload_fields_for(self, asset_type: str) -> list[str]:
        contract = self.contract_for(asset_type)
        return [str(field) for field in contract.get("payload_fields", [])]

    def contract_for(self, asset_type: str) -> dict[str, Any]:
        try:
            return self.contracts[asset_type]
        except KeyError as exc:
            raise KeyError(f"Missing asset contract for asset type: {asset_type}") from exc

    def validate_document(
        self,
        document: dict[str, Any],
        *,
        known_asset_ids: set[str] | None = None,
        require_known_targets: bool = False,
    ) -> AssetContractValidationResult:
        asset_type = str(document.get("asset_type") or document.get("assetType") or "").strip()
        if not asset_type:
            raise ValueError("Asset document must define asset_type")
        contract = self.contract_for(asset_type)
        payload = document.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError("Asset payload must be an object")

        missing = [
            field
            for field in contract.get("required_fields", [])
            if not self._has_field(asset_type, field, document, payload)
        ]
        unsupported = self._unsupported_payload_fields(asset_type, payload, contract)
        invalid_relations = self._invalid_relations(asset_type, document, contract)
        unresolved_targets = self._unresolved_targets(
            document,
            known_asset_ids=known_asset_ids,
            require_known_targets=require_known_targets,
        )
        warnings = self._warnings(asset_type, document, payload, contract)
        return AssetContractValidationResult(
            valid=not missing and not invalid_relations and not unresolved_targets,
            asset_type=asset_type,
            missing_required_fields=missing,
            unsupported_payload_fields=unsupported,
            invalid_relations=invalid_relations,
            unresolved_relation_targets=unresolved_targets,
            warnings=warnings,
        )

    def validate_document_or_raise(
        self,
        document: dict[str, Any],
        *,
        known_asset_ids: set[str] | None = None,
        require_known_targets: bool = False,
    ) -> AssetContractValidationResult:
        result = self.validate_document(
            document,
            known_asset_ids=known_asset_ids,
            require_known_targets=require_known_targets,
        )
        if result.valid:
            return result
        details: list[str] = []
        if result.missing_required_fields:
            details.append(f"missing required fields: {', '.join(result.missing_required_fields)}")
        if result.invalid_relations:
            details.append(
                "invalid relations: "
                + ", ".join(f"{item['type']} for {item['asset_type']}" for item in result.invalid_relations)
            )
        if result.unresolved_relation_targets:
            details.append(
                "unresolved relation targets: "
                + ", ".join(item["target_asset_id"] for item in result.unresolved_relation_targets)
            )
        raise ValueError(f"Asset contract validation failed for {result.asset_type}: {'; '.join(details)}")

    def _has_field(
        self,
        asset_type: str,
        field_name: str,
        document: dict[str, Any],
        payload: dict[str, Any],
    ) -> bool:
        if self._truthy(document.get(field_name)) or self._truthy(payload.get(field_name)):
            return True
        for alias in LEGACY_FIELD_ALIASES.get(asset_type, {}).get(field_name, ()):
            value = document.get(alias) if alias in document else payload.get(alias)
            if field_name == "user_task_refs" and isinstance(value, list):
                return bool(value)
            if self._truthy(value):
                return True
        return False

    def _unsupported_payload_fields(
        self,
        asset_type: str,
        payload: dict[str, Any],
        contract: dict[str, Any],
    ) -> list[str]:
        allowed = set(str(field) for field in contract.get("payload_fields", []))
        allowed.update({"canonical_name", "normalized_name", "aliases", "alignment", "relation_hints"})
        allowed.update({"asset_set_id", "asset_set_version", "domain_id", "module_id", "source_section"})
        allowed.update(LEGACY_FIELD_ALIASES.get(asset_type, {}))
        for aliases in LEGACY_FIELD_ALIASES.get(asset_type, {}).values():
            allowed.update(aliases)
        return sorted(str(field) for field in payload if allowed and field not in allowed)

    def _invalid_relations(
        self,
        asset_type: str,
        document: dict[str, Any],
        contract: dict[str, Any],
    ) -> list[dict[str, str]]:
        relations = document.get("relations") or []
        allowed = set(str(value) for value in ((contract.get("relations") or {}).get("allowed") or []))
        if self.registry is not None:
            allowed.update(self.registry.get_asset_type(asset_type).valid_relations)
        invalid: list[dict[str, str]] = []
        for relation in relations:
            if not isinstance(relation, dict):
                invalid.append({"asset_type": asset_type, "type": "<invalid>", "reason": "relation must be an object"})
                continue
            relation_type = str(relation.get("type") or "").strip()
            if relation_type and allowed and relation_type not in allowed:
                invalid.append(
                    {
                        "asset_type": asset_type,
                        "type": relation_type,
                        "reason": "relation type is not allowed by asset contract or registry",
                    }
                )
        return invalid

    def _unresolved_targets(
        self,
        document: dict[str, Any],
        *,
        known_asset_ids: set[str] | None,
        require_known_targets: bool,
    ) -> list[dict[str, str]]:
        if not require_known_targets:
            return []
        known = known_asset_ids or set()
        unresolved: list[dict[str, str]] = []
        for relation in document.get("relations") or []:
            if not isinstance(relation, dict):
                continue
            target = str(relation.get("target_asset_id") or relation.get("targetAssetId") or "").strip()
            if target and target not in known:
                unresolved.append(
                    {
                        "type": str(relation.get("type") or ""),
                        "target_asset_id": target,
                        "reason": "target asset was not found in the current validation scope",
                    }
                )
        return unresolved

    def _warnings(
        self,
        asset_type: str,
        document: dict[str, Any],
        payload: dict[str, Any],
        contract: dict[str, Any],
    ) -> list[str]:
        warnings: list[str] = []
        unsupported = self._unsupported_payload_fields(asset_type, payload, contract)
        if unsupported:
            warnings.append(f"unsupported payload fields will be preserved but need review: {', '.join(unsupported)}")
        for required in contract.get("required_fields", []):
            aliases = LEGACY_FIELD_ALIASES.get(asset_type, {}).get(str(required), ())
            if aliases and not self._truthy(payload.get(required)) and not self._truthy(document.get(required)):
                if any(self._truthy(document.get(alias) if alias in document else payload.get(alias)) for alias in aliases):
                    warnings.append(f"{required} is satisfied through legacy alias: {', '.join(aliases)}")
        return warnings

    @staticmethod
    def _truthy(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True
