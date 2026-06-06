from pathlib import Path

import yaml

from app.knowledge_base.asset_sets import AssetSetDeploymentService
from app.knowledge_base.catalog_store import AssetCatalogStore
from app.knowledge_base.loader import AssetRegistryLoader
from app.knowledge_base.registry import EnterpriseAssetRegistry


REGISTRY_PATH = Path("config/asset_registry/asset_types.yaml")


def _write_asset_set(root: Path, version: str, label: str) -> Path:
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "module.yaml").write_text(
        yaml.safe_dump(
            {
                "asset_id": "module.loan",
                "asset_type": "module",
                "name": label,
                "version": version,
                "payload": {
                    "moduleId": "loan",
                    "label": label,
                    "domain_id": "lending",
                    "module_id": "loan",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    manifest = {
        "apiVersion": "catalog.unify/v1",
        "kind": "AssetSet",
        "metadata": {
            "id": "loan-module-set",
            "name": "Loan Module Set",
            "version": version,
            "domain": "lending",
            "module": "loan",
        },
        "spec": {
            "assetType": "module",
            "assets": ["assets/module.yaml"],
        },
    }
    path = root / "asset-set.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def _service(tmp_path: Path) -> tuple[AssetSetDeploymentService, AssetCatalogStore]:
    store = AssetCatalogStore(tmp_path / "catalog.sqlite")
    store.initialize()
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    return AssetSetDeploymentService(store=store, registry=registry), store


def test_asset_set_requires_review_before_deployment(tmp_path: Path):
    service, store = _service(tmp_path)
    value = service.load(_write_asset_set(tmp_path / "v1", "1.0.0", "Loans"))

    assert value["status"] == "ready_for_review"

    store.transition_asset_set(
        asset_set_id="loan-module-set",
        version="1.0.0",
        to_status="in_review",
        actor="reviewer",
    )
    validated = store.transition_asset_set(
        asset_set_id="loan-module-set",
        version="1.0.0",
        to_status="validated",
        actor="reviewer",
        comment="Approved.",
    )
    deployment = store.deploy_asset_set(
        asset_set_id="loan-module-set",
        version="1.0.0",
        environment="dev",
        actor="reviewer",
    )

    assert validated["status"] == "validated"
    assert deployment["status"] == "completed"
    assert store.list_active_assets(environment="dev")[0]["asset_id"] == "module.loan"


def test_asset_set_rejects_invalid_transition(tmp_path: Path):
    service, store = _service(tmp_path)
    service.load(_write_asset_set(tmp_path / "v1", "1.0.0", "Loans"))

    try:
        store.transition_asset_set(
            asset_set_id="loan-module-set",
            version="1.0.0",
            to_status="validated",
            actor="reviewer",
        )
    except ValueError as exc:
        assert "ready_for_review -> validated" in str(exc)
    else:
        raise AssertionError("Invalid lifecycle transition was accepted")


def test_asset_set_rollback_reactivates_previous_version(tmp_path: Path):
    service, store = _service(tmp_path)
    for version, label in [("1.0.0", "Loans"), ("1.1.0", "Loans Next")]:
        service.load(_write_asset_set(tmp_path / version, version, label))
        store.transition_asset_set(
            asset_set_id="loan-module-set",
            version=version,
            to_status="in_review",
            actor="reviewer",
        )
        store.transition_asset_set(
            asset_set_id="loan-module-set",
            version=version,
            to_status="validated",
            actor="reviewer",
        )
        store.deploy_asset_set(
            asset_set_id="loan-module-set",
            version=version,
            environment="dev",
            actor="reviewer",
        )

    rollback = store.rollback_asset_set(
        asset_set_id="loan-module-set",
        environment="dev",
        actor="reviewer",
    )

    assert rollback["asset_set_version"] == "1.0.0"
    active = store.list_active_assets(environment="dev")
    assert active[0]["version"] == "1.0.0"


def test_asset_editor_creates_new_immutable_asset_set_version(tmp_path: Path):
    service, store = _service(tmp_path)
    source = _write_asset_set(tmp_path / "loan-module-set", "1.0.0", "Loans")
    service.load(source)

    created = service.create_draft_version(
        asset_id="module.loan",
        base_version="1.0.0",
        actor="developer",
        document={
            "asset_id": "module.loan",
            "asset_type": "module",
            "name": "Loan Operations",
            "description": "Updated in the Lowdefy asset editor.",
            "tags": ["lending", "loan"],
            "relations": [],
            "payload": {
                "moduleId": "loan",
                "label": "Loan Operations",
                "domain_id": "lending",
                "module_id": "loan",
            },
        },
    )

    assert created["version"] == "1.0.1"
    assert created["status"] == "ready_for_review"
    assert store.get_catalog_asset("module.loan", "1.0.0")["name"] == "Loans"
    assert store.get_catalog_asset("module.loan", "1.0.1")["name"] == "Loan Operations"
    generated = tmp_path / "loan-module-set" / "versions" / "1.0.1"
    assert (generated / "asset-set.yaml").is_file()
    assert (generated / "assets" / "module.yaml").is_file()
