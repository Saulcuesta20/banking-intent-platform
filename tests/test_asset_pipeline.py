from pathlib import Path

from app.ingestion.asset_pipeline import CanonicalAssetPipeline
from app.ingestion.llm_flow_loader import CorpusDocument
from app.knowledge_base.loader import AssetRegistryLoader
from app.knowledge_base.registry import EnterpriseAssetRegistry

from conftest import sample_records


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "asset_registry" / "asset_types.yaml"
RELATION_PATTERN_PATH = Path(__file__).resolve().parents[1] / "config" / "ingestion" / "relation_type_patterns.yaml"
ONTOLOGY_PATH = Path(__file__).resolve().parents[1] / "config" / "ontology" / "universal_layers.yaml"


def test_asset_pipeline_extracts_multiple_asset_types_and_owner_kbs():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    pipeline = CanonicalAssetPipeline(
        registry=registry,
        relation_pattern_path=RELATION_PATTERN_PATH,
        ontology_path=ONTOLOGY_PATH,
    )
    documents = [
        CorpusDocument(
            path=Path("operations_controls_policy.md"),
            text=(
                "## Rule: Delinquency threshold\n"
                "Si el cliente tiene mora mayor a treinta dias, no puede refinanciar.\n"
                "No pagar un prestamo causa incumplimiento contractual."
            ),
            kind="text",
        ),
        CorpusDocument(
            path=Path("orchestration_planning_notes.md"),
            text=(
                "## Plan: Preventive collections\n"
                "1. Identificar cuentas vencidas.\n"
                "2. Contactar al cliente.\n"
                "3. Ofrecer arreglo de pago."
            ),
            kind="text",
        ),
    ]
    extraction = {
        "tool_registry": [],
        "user_tasks": [],
        "flows": [],
    }

    assets = pipeline.run(documents=documents, extraction=extraction, records=sample_records("loan.refinance"))
    by_type = {asset.asset_type for asset in assets}

    assert "business_rule" in by_type
    assert "plan" in by_type
    assert "causality" in by_type
    assert "entity" in by_type

    plan = next(asset for asset in assets if asset.asset_type == "plan")
    causality = next(asset for asset in assets if asset.asset_type == "causality")
    entity = next(asset for asset in assets if asset.asset_type == "entity")

    assert plan.owner == "planning_kb"
    assert causality.owner == "causality_kb"
    assert entity.owner == "business_model_kb"
    assert causality.payload["statement"]
    assert any(relation.type == "has_effect" for relation in causality.relations)


def test_asset_pipeline_uses_unified_extraction_asset_arrays():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    pipeline = CanonicalAssetPipeline(
        registry=registry,
        relation_pattern_path=RELATION_PATTERN_PATH,
        ontology_path=ONTOLOGY_PATH,
    )
    extraction = {
        "tool_registry": [],
        "user_tasks": [],
        "flows": [],
        "entity": [{"name": "Prestamo", "aliases": ["credito"], "structural_layer": "transaction"}],
        "business_rule": [
            {
                "name": "Elegibilidad de refinanciamiento",
                "rule_text": "Cuando se solicita refinanciamiento, validar que el prestamo este activo.",
                "when": "loan.refinance.requested",
                "then": "validate eligibility",
                "conditions": ["loan is active"],
                "consequences": ["refinance may continue"],
                "applies_to": ["flow.loan.refinance"],
            }
        ],
        "process": [
            {
                "name": "Refinanciamiento",
                "business_event": "loan.refinance.requested",
                "steps": ["Validar prestamo activo"],
            }
        ],
    }

    assets = pipeline.run(
        documents=[CorpusDocument(path=Path("policy.md"), text="", kind="text")],
        extraction=extraction,
        records=[],
    )

    rule = next(asset for asset in assets if asset.asset_type == "business_rule")
    process = next(asset for asset in assets if asset.asset_type == "process")
    entity = next(asset for asset in assets if asset.asset_type == "entity")

    assert rule.payload["when"] == "loan.refinance.requested"
    assert "validate eligibility" in rule.payload["consequences"]
    assert process.payload["business_event"] == "loan.refinance.requested"
    assert entity.payload["aliases"] == ["credito"]
    assert entity.structural_layer == "transaction"
    assert entity.payload["structural_layer"] == "transaction"
    assert entity.payload["business_layer"] == "transaction"


def test_asset_pipeline_accepts_legacy_concept_and_business_layer():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    pipeline = CanonicalAssetPipeline(
        registry=registry,
        relation_pattern_path=RELATION_PATTERN_PATH,
        ontology_path=ONTOLOGY_PATH,
    )
    extraction = {
        "tool_registry": [],
        "user_tasks": [],
        "flows": [],
        "concept": [{"name": "Core Banking Platform", "aliases": ["CBS"], "business_layer": "asset"}],
    }

    assets = pipeline.run(
        documents=[CorpusDocument(path=Path("legacy.md"), text="", kind="text")],
        extraction=extraction,
        records=[],
    )

    entity = next(asset for asset in assets if asset.asset_type == "entity")

    assert entity.asset_id == "entity.core_banking_platform"
    assert entity.structural_layer == "business_resource"
    assert entity.payload["structural_layer"] == "business_resource"


def test_asset_pipeline_preserves_technical_entity_shape_and_relation_aliases():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    pipeline = CanonicalAssetPipeline(
        registry=registry,
        relation_pattern_path=RELATION_PATTERN_PATH,
        ontology_path=ONTOLOGY_PATH,
    )
    extraction = {
        "tool_registry": [],
        "user_tasks": [],
        "flows": [],
        "entity": [
            {
                "name": "gold.customers",
                "structural_layer": "business_resource",
                "subtype": "table",
                "technical_type": "table",
                "relations": [{"type": "materializes", "target": "entity.customer"}],
                "attributes": [{"name": "customer_id", "type": "string", "identifier": True}],
            }
        ],
    }

    assets = pipeline.run(
        documents=[CorpusDocument(path=Path("tables.md"), text="", kind="text")],
        extraction=extraction,
        records=[],
    )

    table_entity = next(asset for asset in assets if asset.asset_type == "entity")

    assert table_entity.payload["subtype"] == "table"
    assert table_entity.payload["technical_type"] == "table"
    assert table_entity.payload["attributes"][0]["name"] == "customer_id"
    assert any(relation.type == "represents" for relation in table_entity.relations)
    assert all(relation.type != "materializes" for relation in table_entity.relations)


def test_asset_pipeline_hydrates_container_asset_contracts():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    pipeline = CanonicalAssetPipeline(
        registry=registry,
        relation_pattern_path=RELATION_PATTERN_PATH,
        ontology_path=ONTOLOGY_PATH,
    )
    extraction = {
        "tool_registry": [],
        "user_tasks": [],
        "flows": [],
        "domain": [{"domain_id": "lending", "name": "Lending", "purpose": "Loan products"}],
        "module": [{"module_id": "loan", "domain_id": "lending", "name": "Loan", "purpose": "Loan operations"}],
        "menu": [{"menu_id": "loan-refinance", "module_id": "loan", "label": "Refinance", "path": "/loan/refinance"}],
        "asset_set": [
            {
                "asset_set_id": "loan-flow-set",
                "version": "1.0.0",
                "primary_asset_type": "flow",
                "members": [{"asset_id": "flow.loan.refinance", "asset_type": "flow"}],
            }
        ],
    }

    assets = pipeline.run(
        documents=[CorpusDocument(path=Path("config.md"), text="", kind="text")],
        extraction=extraction,
        records=[],
    )

    module = next(asset for asset in assets if asset.asset_type == "module")
    menu = next(asset for asset in assets if asset.asset_type == "menu")
    asset_set = next(asset for asset in assets if asset.asset_type == "asset_set")

    assert any(relation.type == "belongs_to_domain" for relation in module.relations)
    assert any(relation.type == "belongs_to_module" for relation in menu.relations)
    assert any(relation.type == "groups_flow" for relation in asset_set.relations)
