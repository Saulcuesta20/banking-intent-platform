from pathlib import Path

import yaml

from app.ingestion.staging import IngestionAssetSetStager
from app.knowledge_base.models import EnterpriseAsset


def test_ingestion_asset_set_stager_populates_members_from_asset_ids(tmp_path: Path):
    stager = IngestionAssetSetStager(tmp_path)
    asset = EnterpriseAsset(
        asset_id="ingest-run-flow-set",
        asset_type="asset_set",
        name="Ingestion flow candidates",
        payload={
            "asset_ids": ["flow.alpha", "user_task.review"],
            "primary_asset_type": "flow",
        },
    )

    [staged] = stager.write_run(run_id="run-001", assets=[asset])
    document = yaml.safe_load(
        (staged.manifest_path.parent / "assets" / "ingest-run-flow-set.yaml").read_text(encoding="utf-8")
    )

    assert document["payload"]["primary_asset_type"] == "flow"
    assert document["payload"]["members"] == [
        {"asset_id": "flow.alpha"},
        {"asset_id": "user_task.review"},
    ]
