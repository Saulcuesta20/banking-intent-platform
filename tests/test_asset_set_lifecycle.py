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
            "description": "Updated in the asset editor.",
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


def test_asset_editor_preview_diff_and_projection_are_read_only(tmp_path: Path):
    service, store = _service(tmp_path)
    source = _write_asset_set(tmp_path / "loan-module-set", "1.0.0", "Loans")
    service.load(source)

    preview = service.preview_draft_version(
        asset_id="module.loan",
        base_version="1.0.0",
        document={
            "asset_id": "module.loan",
            "asset_type": "module",
            "name": "Loan Operations",
            "description": "Updated before save.",
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

    assert preview["draft_version"] == "1.0.1"
    assert preview["validation"]["valid"] is True
    assert preview["diff"]["changed"] is True
    assert "repository" in preview["projection_preview"]["stores"]
    assert store.get_catalog_asset("module.loan", "1.0.1") is None


def test_asset_editor_diff_between_existing_versions(tmp_path: Path):
    service, _store = _service(tmp_path)
    source = _write_asset_set(tmp_path / "loan-module-set", "1.0.0", "Loans")
    service.load(source)
    service.create_draft_version(
        asset_id="module.loan",
        base_version="1.0.0",
        actor="developer",
        document={
            "asset_id": "module.loan",
            "asset_type": "module",
            "name": "Loan Operations",
            "description": "Updated in the asset editor.",
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

    diff = service.diff_asset_versions(
        asset_id="module.loan",
        from_version="1.0.0",
        to_version="1.0.1",
    )

    assert diff["diff"]["changed"] is True
    assert any(change["field"] == "name" for change in diff["diff"]["fields"])


def test_asset_contract_validation_rejects_missing_required_payload(tmp_path: Path):
    service, _store = _service(tmp_path)
    source = _write_asset_set(tmp_path / "loan-module-set", "1.0.0", "Loans")
    asset_path = source.parent / "assets" / "module.yaml"
    document = yaml.safe_load(asset_path.read_text(encoding="utf-8"))
    document["payload"].pop("domain_id")
    document["payload"].pop("module_id")
    document["payload"].pop("label")
    document.pop("description", None)
    asset_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    try:
        service.load(source)
    except ValueError as exc:
        assert "missing required fields" in str(exc)
        assert "purpose" in str(exc)
    else:
        raise AssertionError("AssetSet load accepted a document that violates its contract")


def test_asset_contract_validation_rejects_invalid_relation(tmp_path: Path):
    service, _store = _service(tmp_path)
    source = _write_asset_set(tmp_path / "loan-module-set", "1.0.0", "Loans")
    asset_path = source.parent / "assets" / "module.yaml"
    document = yaml.safe_load(asset_path.read_text(encoding="utf-8"))
    document["relations"] = [{"type": "implemented_by_process", "target_asset_id": "process.loan"}]
    asset_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    try:
        service.load(source)
    except ValueError as exc:
        assert "invalid relations" in str(exc)
        assert "implemented_by_process" in str(exc)
    else:
        raise AssertionError("AssetSet load accepted a relation outside the contract")


def test_asset_validate_returns_contract_warnings_for_legacy_payload(tmp_path: Path):
    service, _store = _service(tmp_path)

    validation = service.validate_asset_document(
        document={
            "asset_id": "flow.loan.refinance",
            "asset_type": "flow",
            "name": "Loan Refinance",
            "description": "Legacy flow description.",
            "relations": [],
            "payload": {
                "flow_id": "loan.refinance",
                "flow_name": "Loan Refinance",
                "intent": "refinance my loan",
                "business_event": "loan.refinance.requested",
                "user_tasks": [{"user_task_id": "review_refinance_options"}],
            },
        },
    )

    assert validation["valid"] is True
    assert validation["contract_validation"]["valid"] is True
    assert any("purpose" in warning for warning in validation["warnings"])
