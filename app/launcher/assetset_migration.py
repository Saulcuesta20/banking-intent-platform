from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def export_legacy_launcher_asset_sets(modules_directory: Path) -> list[Path]:
    """Convert the current launcher JSON authoring folders into AssetSet YAML."""
    domains_path = modules_directory / "domains.json"
    domains = json.loads(domains_path.read_text(encoding="utf-8"))
    written: list[Path] = []
    navigation_assets = [
        {
            "asset_id": f"domain.{domain['domainId']}",
            "asset_type": "domain",
            "name": domain["label"],
            "description": domain["description"],
            "tags": [domain["domainId"], "launcher"],
            "payload": domain,
        }
        for domain in domains
    ]
    written.append(
        _write_asset_set(
            root=modules_directory / "platform" / "assetsets" / "domain-set",
            asset_set_id="launcher-domain-set",
            name="Launcher Domain Set",
            version="1.0.0",
            domain="platform",
            module="launcher",
            asset_type="domain",
            assets=navigation_assets,
        )
    )

    for domain in domains:
        domain_id = str(domain["domainId"])
        domain_directory = modules_directory / domain_id
        if not domain_directory.exists():
            continue
        for module_directory in sorted(path for path in domain_directory.iterdir() if path.is_dir()):
            module_path = module_directory / "module.json"
            if not module_path.exists():
                continue
            module = json.loads(module_path.read_text(encoding="utf-8"))
            module_id = str(module["moduleId"])
            target_root = modules_directory / module_id / "assetsets"
            module_asset = {
                "asset_id": f"module.{module_id}",
                "asset_type": "module",
                "name": module["label"],
                "description": module["description"],
                "tags": [domain_id, module_id, "launcher"],
                "relations": [
                    {"type": "belongs_to_domain", "target_asset_id": f"domain.{domain_id}"}
                ],
                "payload": {**module, "domainId": domain_id},
            }
            written.append(
                _write_asset_set(
                    root=target_root / "module-set",
                    asset_set_id=f"{module_id}-module-set",
                    name=f"{module['label']} Module Set",
                    version="1.0.0",
                    domain=domain_id,
                    module=module_id,
                    asset_type="module",
                    assets=[module_asset],
                )
            )
            menu_assets = _menu_assets(module, domain_id=domain_id, module_id=module_id)
            if menu_assets:
                written.append(
                    _write_asset_set(
                        root=target_root / "menu-set",
                        asset_set_id=f"{module_id}-menu-set",
                        name=f"{module['label']} Menu Set",
                        version="1.0.0",
                        domain=domain_id,
                        module=module_id,
                        asset_type="menu",
                        assets=menu_assets,
                    )
                )
            flows, processes, forms = _business_assets(module_directory, domain_id, module_id)
            for folder, suffix, label, asset_type, assets in [
                ("flow-set", "flow-set", "Flow Set", "flow", flows),
                ("process-set", "process-set", "Process Set", "process", processes),
                ("form-set", "form-set", "Form Set", "form", forms),
            ]:
                if not assets:
                    continue
                written.append(
                    _write_asset_set(
                        root=target_root / folder,
                        asset_set_id=f"{module_id}-{suffix}",
                        name=f"{module['label']} {label}",
                        version="1.0.0",
                        domain=domain_id,
                        module=module_id,
                        asset_type=asset_type,
                        assets=assets,
                    )
                )
    return written


def _business_assets(
    module_directory: Path,
    domain_id: str,
    module_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    flows: list[dict[str, Any]] = []
    processes: list[dict[str, Any]] = []
    forms: list[dict[str, Any]] = []
    processes_directory = module_directory / "processes"
    if not processes_directory.exists():
        return flows, processes, forms
    for process_directory in sorted(path for path in processes_directory.iterdir() if path.is_dir()):
        config = json.loads((process_directory / "process.json").read_text(encoding="utf-8"))
        flow_id = str(config["processId"])
        process_asset_id = f"process.{flow_id}"
        flows.append(
            {
                "asset_id": f"flow.{flow_id}",
                "asset_type": "flow",
                "name": config["name"],
                "description": config["intent"],
                "tags": [domain_id, module_id, "flow"],
                "relations": [
                    {"type": "implemented_by_process", "target_asset_id": process_asset_id}
                ],
                "payload": {
                    "flow_id": flow_id,
                    "flow_name": config["name"],
                    "intent": config["intent"],
                    "business_event": config["businessEvent"],
                    "domain_id": domain_id,
                    "module_id": module_id,
                    "renderer": "external",
                    "user_tasks": config.get("userTasks") or [],
                    "related_process_ids": config.get("processIds") or [flow_id],
                },
            }
        )
        processes.append(
            {
                "asset_id": process_asset_id,
                "asset_type": "process",
                "name": config["name"],
                "description": config["intent"],
                "tags": [domain_id, module_id, "process"],
                "relations": [
                    {"type": "implements_flow", "target_asset_id": f"flow.{flow_id}"}
                ],
                "payload": {
                    "process_id": flow_id,
                    "process_name": config["name"],
                    "domain": domain_id,
                    "module_id": module_id,
                    "business_event": config["businessEvent"],
                    "user_tasks": config.get("userTasks") or [],
                },
            }
        )
        form_path = (
            module_directory
            / "forms"
            / str(config["formId"])
            / "versions"
            / str(config["currentFormVersion"])
            / "form.json"
        )
        if form_path.exists():
            form = json.loads(form_path.read_text(encoding="utf-8"))
            forms.append(
                {
                    "asset_id": f"form.{form['formId']}",
                    "asset_type": "form",
                    "name": form["title"],
                    "version": form["version"],
                    "description": f"Versioned form definition for {module_id}.",
                    "tags": [domain_id, module_id, "form", "jsonforms"],
                    "payload": {
                        **form,
                        "domain_id": domain_id,
                        "module_id": module_id,
                        "renderer": "react",
                        "binding_status": "phase_two",
                    },
                }
            )
    return flows, processes, forms


def _menu_assets(module: dict[str, Any], *, domain_id: str, module_id: str) -> list[dict[str, Any]]:
    menus = module.get("menus") or []
    if not menus:
        menus = [
            {"id": "queries", "label": "Consultas"},
            {"id": "operations", "label": "Operaciones"},
            {"id": "configuration", "label": "Configuracion"},
        ]
    return [
        {
            "asset_id": f"menu.{module_id}.{menu['id']}",
            "asset_type": "menu",
            "name": menu["label"],
            "description": f"{module['label']} launcher menu.",
            "tags": [domain_id, module_id, "menu"],
            "relations": [
                {"type": "belongs_to_module", "target_asset_id": f"module.{module_id}"}
            ],
            "payload": {**menu, "module_id": module_id, "domain_id": domain_id},
        }
        for menu in menus
    ]


def _write_asset_set(
    *,
    root: Path,
    asset_set_id: str,
    name: str,
    version: str,
    domain: str,
    module: str,
    asset_type: str,
    assets: list[dict[str, Any]],
) -> Path:
    assets_directory = root / "assets"
    assets_directory.mkdir(parents=True, exist_ok=True)
    asset_files = []
    for asset in assets:
        filename = f"{str(asset['asset_id']).replace('.', '-')}.yaml"
        path = assets_directory / filename
        path.write_text(yaml.safe_dump(asset, sort_keys=False, allow_unicode=False), encoding="utf-8")
        asset_files.append(f"assets/{filename}")
    manifest = {
        "apiVersion": "catalog.unify/v1",
        "kind": "AssetSet",
        "metadata": {
            "id": asset_set_id,
            "name": name,
            "version": version,
            "domain": domain,
            "module": module,
            "description": f"Versioned {asset_type} deployment set for {module}.",
            "tags": [domain, module, asset_type],
        },
        "spec": {
            "assetType": asset_type,
            "assets": asset_files,
        },
    }
    manifest_path = root / "asset-set.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return manifest_path


__all__ = ["export_legacy_launcher_asset_sets"]
