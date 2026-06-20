from pathlib import Path

import pytest

from app.knowledge_base.loader import AssetRegistryLoader
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.search import AssetSearchService
from app.knowledge_base.registry import EnterpriseAssetRegistry
from app.factory import (
    build_asset_search_service,
    build_enterprise_asset_registry,
    build_enterprise_asset_repository,
)
from conftest import sample_assets


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "asset_registry" / "asset_types.yaml"


def test_asset_registry_loads_yaml_configuration():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))

    assert "flow" in registry.list_asset_types()
    assert "business_rule" in registry.list_asset_types()
    assert "graph" in registry.list_knowledge_bases()
    assert "vector" in registry.list_knowledge_bases()


def test_asset_registry_exposes_routing_behavior():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))

    assert registry.is_direct_route("flow") is True
    assert registry.route_kind_for("flow") == "flow_route"
    assert registry.is_direct_route("process") is True
    assert registry.route_kind_for("process") == "process_route"
    assert registry.is_direct_route("qa") is True
    assert registry.route_kind_for("qa") == "qa_route"
    assert registry.is_consultable_route("business_rule") is True
    assert registry.is_supporting_asset("plan") is True


def test_asset_registry_maps_asset_types_to_knowledge_bases():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))

    assert registry.stores_for("business_rule") == ["repository", "document", "graph", "vector"]
    assert registry.stores_for("process") == ["repository", "graph"]
    assert registry.owner_kb_for("process") == "process_kb"
    assert registry.owner_kb_for("plan") == "planning_kb"
    assert registry.owner_kb_for("causality") == "causality_kb"
    assert "qa" in registry.asset_types_for_store("vector")
    assert "business_rule" in registry.asset_types_for_store("vector")
    assert "process" not in registry.asset_types_for_store("vector")


def test_asset_registry_validates_unknown_store_references():
    with pytest.raises(ValueError, match="unknown knowledge stores"):
        AssetRegistryLoader().load_dict(
            {
                "stores": {"graph": {"role": "relationship_index"}},
                "asset_types": {
                    "rule": {
                        "stores": ["missing"],
                    }
                },
            }
        )


def test_factory_builds_enterprise_asset_registry():
    registry = build_enterprise_asset_registry()

    assert registry.is_consultable_route("business_rule") is True
    assert registry.is_executable("process") is True


def test_enterprise_asset_repository_lists_assets():
    repository = EnterpriseAssetRepository(sample_assets())

    assert repository.get("qa.automatic_payment_account_required") is not None
    assert repository.get("business_rule.refinance_eligibility") is not None
    assert repository.get("plan.loan_refinance") is not None
    assert [asset.asset_id for asset in repository.list_assets("plan", approved_only=False)] == [
        "plan.loan_refinance",
        "plan.savings_account_opening",
    ]


def test_asset_search_groups_direct_consultable_and_supporting_assets():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    repository = EnterpriseAssetRepository(sample_assets())
    service = AssetSearchService(registry, repository)

    result = service.search("Necesito una cuenta para pago automatico?", approved_only=False)

    assert "qa.automatic_payment_account_required" in [
        asset.asset_id for asset in result.primary_assets
    ]
    assert "business_rule.automatic_payment_account_required" in [
        asset.asset_id for asset in result.supporting_assets
    ]
    assert "plan.savings_account_opening" in [
        asset.asset_id for asset in result.evidence_assets
    ]


def test_asset_search_resolves_related_assets():
    service = build_asset_search_service()

    related = service.related_assets("business_rule.automatic_payment_account_requirement")

    assert isinstance(related, list)


def test_factory_builds_enterprise_asset_repository():
    repository = build_enterprise_asset_repository()

    assert any(asset.asset_type == "plan" for asset in repository.list_assets(approved_only=False))
