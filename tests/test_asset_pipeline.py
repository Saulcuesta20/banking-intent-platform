from pathlib import Path

from app.ingestion.asset_pipeline import CanonicalAssetPipeline
from app.ingestion.llm_flow_loader import CorpusDocument
from app.knowledge_base.loader import AssetRegistryLoader
from app.knowledge_base.registry import EnterpriseAssetRegistry

from conftest import sample_records


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "asset_registry" / "asset_types.yaml"
RELATION_PATTERN_PATH = Path(__file__).resolve().parents[1] / "config" / "ingestion" / "relation_type_patterns.yaml"


def test_asset_pipeline_extracts_multiple_asset_types_and_owner_kbs():
    registry = EnterpriseAssetRegistry(AssetRegistryLoader().load_file(REGISTRY_PATH))
    pipeline = CanonicalAssetPipeline(
        registry=registry,
        relation_pattern_path=RELATION_PATTERN_PATH,
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
    assert any(relation.type == "has_effect" for relation in causality.relations)
