from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.knowledge_base.catalog_store import AssetCatalogStore


@dataclass(frozen=True)
class LauncherRuntimeService:
    """Build launcher views from active Unified Catalog AssetSet deployments."""

    catalog: AssetCatalogStore
    environment: str = "dev"

    def home(self) -> dict[str, Any]:
        assets = self.catalog.list_active_assets(environment=self.environment)
        domains = [self._domain(asset) for asset in assets if asset["asset_type"] == "domain"]
        modules = [self._module(asset) for asset in assets if asset["asset_type"] == "module"]
        flows = [self._flow(asset) for asset in assets if asset["asset_type"] == "flow"]
        menus = [asset for asset in assets if asset["asset_type"] == "menu"]
        menu_by_module: dict[str, list[dict[str, Any]]] = {}
        for menu in menus:
            module_id = str(menu.get("module_id") or menu["payload"].get("payload", {}).get("module_id") or "")
            menu_by_module.setdefault(module_id, []).append(self._menu(menu))
        flow_counts: dict[str, int] = {}
        for flow in flows:
            module_id = str(flow.get("module_id") or "")
            flow_counts[module_id] = flow_counts.get(module_id, 0) + 1
        domain_labels = {domain["domainId"]: domain["label"] for domain in domains}
        for module in modules:
            module_id = str(module["module_id"])
            module["menus"] = menu_by_module.get(module_id, module.get("menus") or [])
            module["flow_count"] = flow_counts.get(module_id, 0)
            module["domain_label"] = domain_labels.get(str(module.get("domain_id")), str(module.get("domain_id") or ""))
        return {
            "modules": [self._system_module("home"), *modules, self._system_module("admin")],
            "featured_flows": flows,
            "recent_flows": [],
            "navigation": {
                "source": "unified_catalog",
                "environment": self.environment,
                "domains": sorted(domains, key=lambda item: item.get("order", 999)),
                "module_count": len(modules),
            },
        }

    def flow_context(self, flow_id: str) -> dict[str, Any]:
        candidates = self.catalog.list_catalog_assets(
            environment=self.environment,
            asset_type="flow",
            active_only=True,
            status="all",
            limit=10_000,
        )
        asset = next(
            (
                item
                for item in candidates
                if item["asset_id"] in {flow_id, f"flow.{flow_id}"}
                or str(self._body(item).get("flow_id") or "") == flow_id
            ),
            None,
        )
        if asset is None:
            raise KeyError(f"Active catalog flow not found: {flow_id}")
        summary = self._flow(asset)
        detail = self.catalog.get_catalog_asset(asset["asset_id"], asset["version"])
        return {
            "flow": summary,
            "module": self._find_active("module", str(summary.get("module_id") or "")),
            "process": self._related_asset(detail, "executes_process"),
            "form": None,
            "form_version": None,
            "renderer": summary.get("renderer"),
            "lowdefy_page": summary.get("lowdefy_page"),
            "lowdefy_url": (
                f"http://localhost:3002/{summary['lowdefy_page']}"
                if summary.get("lowdefy_page")
                else None
            ),
        }

    def _find_active(self, asset_type: str, identifier: str) -> dict[str, Any] | None:
        for asset in self.catalog.list_active_assets(environment=self.environment, asset_type=asset_type):
            body = self._body(asset)
            if identifier in {
                asset["asset_id"],
                asset["asset_id"].removeprefix(f"{asset_type}."),
                str(body.get(f"{asset_type}_id") or body.get(f"{asset_type}Id") or ""),
            }:
                return self._module(asset) if asset_type == "module" else body
        return None

    def _related_asset(self, detail: dict[str, Any] | None, relation_type: str) -> dict[str, Any] | None:
        if not detail:
            return None
        relation = next(
            (item for item in detail.get("relationships") or [] if item["type"] == relation_type),
            None,
        )
        if relation is None:
            return None
        return self.catalog.get_catalog_asset(str(relation["target_asset_id"]))

    @staticmethod
    def _body(asset: dict[str, Any]) -> dict[str, Any]:
        payload = asset.get("payload") or {}
        return dict(payload.get("payload") or payload)

    def _domain(self, asset: dict[str, Any]) -> dict[str, Any]:
        body = self._body(asset)
        return {
            "domainId": body.get("domainId") or body.get("domain_id") or asset["asset_id"].removeprefix("domain."),
            "label": body.get("label") or asset.get("name") or asset["asset_id"],
            "description": body.get("description") or "",
            "order": body.get("order", 999),
        }

    def _module(self, asset: dict[str, Any]) -> dict[str, Any]:
        body = self._body(asset)
        module_id = str(body.get("moduleId") or body.get("module_id") or asset["asset_id"].removeprefix("module."))
        return {
            "module_id": module_id,
            "label": body.get("label") or asset.get("name") or module_id,
            "description": body.get("description") or "",
            "icon": body.get("icon") or "module",
            "aliases": body.get("aliases") or asset.get("tags") or [],
            "flow_prefixes": [module_id],
            "menus": body.get("menus") or [],
            "top_menus": body.get("topMenus") or body.get("top_menus") or [],
            "flow_count": 0,
            "domain_id": asset.get("domain_id") or body.get("domainId") or body.get("domain_id"),
            "domain_label": "",
        }

    def _menu(self, asset: dict[str, Any]) -> dict[str, Any]:
        body = self._body(asset)
        return {
            "id": body.get("id") or asset["asset_id"].removeprefix("menu."),
            "label": body.get("label") or asset.get("name"),
            "path": body.get("path"),
            "icon": body.get("icon"),
            "children": body.get("children") or [],
        }

    def _flow(self, asset: dict[str, Any]) -> dict[str, Any]:
        body = self._body(asset)
        flow_id = str(body.get("flow_id") or asset["asset_id"].removeprefix("flow."))
        return {
            "module_id": asset.get("module_id") or body.get("module_id") or flow_id.split(".", 1)[0],
            "flow_id": flow_id,
            "flow_name": body.get("flow_name") or asset.get("name") or flow_id,
            "intent": body.get("intent") or "",
            "business_event": body.get("business_event") or "",
            "source_path": None,
            "source_type": "unified_catalog",
            "plan_steps": len(body.get("user_tasks") or []),
            "user_tasks": body.get("user_tasks") or [],
            "related_process_ids": body.get("related_process_ids") or [],
            "confidence": 1,
            "explanation": body.get("description") or body.get("intent") or "",
            "renderer": body.get("renderer") or "external",
            "lowdefy_page": body.get("lowdefy_page"),
            "module_config_id": asset.get("module_id"),
            "form_id": None,
            "form_version": None,
            "domain_id": asset.get("domain_id"),
            "domain_label": asset.get("domain_id"),
            "asset_set_id": asset.get("asset_set_id"),
            "asset_set_version": asset.get("asset_set_version"),
        }

    @staticmethod
    def _system_module(module_id: str) -> dict[str, Any]:
        if module_id == "home":
            return {
                "module_id": "home",
                "label": "Home",
                "description": "Workspace principal del launcher.",
                "icon": "home",
                "aliases": ["inicio"],
                "flow_prefixes": [],
                "menus": [],
                "top_menus": [],
                "flow_count": 0,
                "domain_id": "all",
                "domain_label": "Todos",
            }
        return {
            "module_id": "admin",
            "label": "Admin",
            "description": "Gobierno, permisos y configuracion.",
            "icon": "settings",
            "aliases": ["administracion"],
            "flow_prefixes": [],
            "menus": [],
            "top_menus": [],
            "flow_count": 0,
            "domain_id": "all",
            "domain_label": "Todos",
        }


__all__ = ["LauncherRuntimeService"]
