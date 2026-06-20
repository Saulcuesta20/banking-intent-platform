from __future__ import annotations

import subprocess
import json
from pathlib import Path

import typer
import uvicorn
import yaml

from app.factory import (
    build_asset_catalog_store,
    build_asset_set_deployment_service,
)
from app.config.settings import load_settings
from app.launcher.assetset_migration import export_legacy_launcher_asset_sets

app = typer.Typer(help="Launcher commands for the Enterprise AI Launcher.")
start_app = typer.Typer(help="Launcher startup commands.")
assets_app = typer.Typer(help="AssetSet authoring, review, and deployment commands.")
LAUNCHER_DIR = Path(__file__).parent / "launcher"


def _asset_source_path() -> Path:
    return load_settings().asset_source_path


@start_app.command("engine")
def start_engine(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development."),
) -> None:
    """Start the backend engine."""
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@start_app.command("ui")
def start_ui() -> None:
    """Start the React/TypeScript launcher shell."""
    subprocess.run(["npm", "run", "dev"], cwd=LAUNCHER_DIR, check=True)


app.add_typer(start_app, name="start")
app.add_typer(assets_app, name="assets")


@app.command("status")
def status() -> None:
    """Print launcher shell status."""
    package_json = LAUNCHER_DIR / "package.json"
    typer.echo(f"launcher ui: {LAUNCHER_DIR}")
    typer.echo(f"package.json: {'ok' if package_json.exists() else 'missing'}")


@app.command("publish")
def publish() -> None:
    """Backward-compatible alias for loading AssetSets into Unified Catalog."""
    values = build_asset_set_deployment_service().load_directory(_asset_source_path())
    typer.echo(f"launcher AssetSets loaded for review: {len(values)}")


@assets_app.command("export")
def export_asset_sets() -> None:
    """Export existing launcher JSON definitions into AssetSet YAML folders."""
    paths = export_legacy_launcher_asset_sets(LAUNCHER_DIR / "modules")
    typer.echo(f"asset sets exported: {len(paths)}")
    for path in paths:
        typer.echo(str(path))


@assets_app.command("load")
def load_asset_sets(
    root: Path | None = typer.Option(None, "--root"),
) -> None:
    """Validate AssetSet YAML and register versions as ready for review."""
    values = build_asset_set_deployment_service().load_directory(root or _asset_source_path())
    typer.echo(f"asset sets loaded: {len(values)}")


@assets_app.command("approve-baseline")
def approve_baseline(
    environment: str = typer.Option("dev", "--environment"),
    actor: str = typer.Option("migration", "--actor"),
) -> None:
    """Review, validate, and deploy the initial imported AssetSet baseline."""
    store = build_asset_catalog_store()
    deployment_service = build_asset_set_deployment_service()
    values = store.list_asset_sets(environment=environment, status="all")
    deployed = 0
    for item in values:
        asset_set_id = str(item["asset_set_id"])
        version = str(item["version"])
        status = str(item["status"])
        if status == "ready_for_review":
            store.transition_asset_set(
                asset_set_id=asset_set_id,
                version=version,
                to_status="in_review",
                actor=actor,
                comment="Initial catalog migration review.",
            )
            status = "in_review"
        if status == "in_review":
            store.transition_asset_set(
                asset_set_id=asset_set_id,
                version=version,
                to_status="validated",
                actor=actor,
                comment="Initial baseline validated.",
            )
            status = "validated"
        if status == "validated":
            deployment_service.deploy(
                asset_set_id=asset_set_id,
                version=version,
                environment=environment,
                actor=actor,
            )
            deployed += 1
    typer.echo(f"asset sets deployed to {environment}: {deployed}")


@assets_app.command("status")
def asset_set_status(
    environment: str = typer.Option("dev", "--environment"),
) -> None:
    """List AssetSet versions and their active environment."""
    values = build_asset_catalog_store().list_asset_sets(environment=environment, status="all")
    typer.echo(json.dumps(values, indent=2, ensure_ascii=False))


@assets_app.command("plan")
def asset_set_plan(
    asset_set_id: str,
    version: str,
    environment: str = typer.Option("dev", "--environment"),
) -> None:
    """Show the candidate members and projections without changing runtime state."""
    value = build_asset_catalog_store().get_asset_set(asset_set_id, version)
    if value is None:
        raise typer.BadParameter(f"Unknown AssetSet version: {asset_set_id}@{version}")
    stores = sorted({store for member in value["members"] for store in member.get("stores") or []})
    plan = {
        "asset_set_id": asset_set_id,
        "version": version,
        "status": value["status"],
        "environment": environment,
        "deployable": value["status"] in {"validated", "active"},
        "member_count": len(value["members"]),
        "projections": stores,
        "checksum": value["checksum"],
    }
    typer.echo(json.dumps(plan, indent=2, ensure_ascii=False))


@assets_app.command("transition")
def asset_set_transition(
    asset_set_id: str,
    version: str,
    to_status: str = typer.Option(..., "--to"),
    actor: str = typer.Option(..., "--actor"),
    comment: str | None = typer.Option(None, "--comment"),
) -> None:
    """Apply one guarded lifecycle transition."""
    value = build_asset_catalog_store().transition_asset_set(
        asset_set_id=asset_set_id,
        version=version,
        to_status=to_status,
        actor=actor,
        comment=comment,
    )
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False))


@assets_app.command("deploy")
def asset_set_deploy(
    asset_set_id: str,
    version: str,
    environment: str = typer.Option("dev", "--environment"),
    actor: str = typer.Option(..., "--actor"),
) -> None:
    """Project and activate one validated AssetSet version."""
    value = build_asset_set_deployment_service().deploy(
        asset_set_id=asset_set_id,
        version=version,
        environment=environment,
        actor=actor,
    )
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False))


@assets_app.command("rollback")
def asset_set_rollback(
    asset_set_id: str,
    environment: str = typer.Option("dev", "--environment"),
    actor: str = typer.Option(..., "--actor"),
) -> None:
    """Reactivate the previously deployed AssetSet version."""
    value = build_asset_catalog_store().rollback_asset_set(
        asset_set_id=asset_set_id,
        environment=environment,
        actor=actor,
    )
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False))


@assets_app.command("diff")
def asset_set_diff(
    asset_set_id: str,
    from_version: str = typer.Option(..., "--from"),
    to_version: str = typer.Option(..., "--to"),
) -> None:
    """Compare exact member versions between two AssetSet versions."""
    store = build_asset_catalog_store()
    before = store.get_asset_set(asset_set_id, from_version)
    after = store.get_asset_set(asset_set_id, to_version)
    if before is None or after is None:
        raise typer.BadParameter("Both AssetSet versions must exist")
    before_members = {item["asset_id"]: item["version"] for item in before["members"]}
    after_members = {item["asset_id"]: item["version"] for item in after["members"]}
    payload = {
        "added": sorted(asset_id for asset_id in after_members if asset_id not in before_members),
        "removed": sorted(asset_id for asset_id in before_members if asset_id not in after_members),
        "changed": sorted(
            asset_id
            for asset_id in before_members.keys() & after_members.keys()
            if before_members[asset_id] != after_members[asset_id]
        ),
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@assets_app.command("pull")
def asset_set_pull(
    asset_set_id: str,
    version: str,
    output: Path = typer.Option(Path("exported-assetsets"), "--output"),
) -> None:
    """Export one catalog AssetSet version back to portable YAML."""
    value = build_asset_catalog_store().get_asset_set(asset_set_id, version)
    if value is None:
        raise typer.BadParameter(f"Unknown AssetSet version: {asset_set_id}@{version}")
    root = output / asset_set_id / version
    assets_directory = root / "assets"
    assets_directory.mkdir(parents=True, exist_ok=True)
    asset_paths = []
    for member in value["members"]:
        filename = f"{member['asset_id'].replace('.', '-')}.yaml"
        asset_paths.append(f"assets/{filename}")
        payload = member["payload"]
        (assets_directory / filename).write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
    manifest = {
        "apiVersion": value["metadata"].get("api_version", "catalog.unify/v1"),
        "kind": "AssetSet",
        "metadata": {
            "id": value["asset_set_id"],
            "name": value["name"],
            "version": value["version"],
            "domain": value["domain_id"],
            "module": value["module_id"],
            "description": value["description"],
            "git_commit": value["git_commit"],
            "tags": value["metadata"].get("tags") or [],
        },
        "spec": {
            "assetType": value["asset_type"],
            "assets": asset_paths,
        },
    }
    manifest_path = root / "asset-set.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    typer.echo(str(manifest_path))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
