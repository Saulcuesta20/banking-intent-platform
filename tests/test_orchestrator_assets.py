from app.knowledge_base.models import AssetRelation, EnterpriseAsset
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.knowledge_base.service import KnowledgeBaseService
from app.models import KnowledgeRecord, Task, UserTask
from app.orchestrator.assets import OrchestratorAssetRegistry


class FakeKnowledgeBaseRepository:
    def __init__(self, records):
        self.records = records

    def search(self, search_terms):
        return self.records

    def list_all_records(self):
        return self.records

    def initialize(self):
        return None

    def upsert_record(self, record):
        return None


def test_orchestrator_asset_registry_lists_flows_processes_and_links():
    flow = KnowledgeRecord(
        flow_id="money.transfer",
        flow_name="Money Transfer",
        intent="money.transfer",
        confidence=0.8,
        business_event="MoneyTransferRequested",
        utterances=["quiero transferir dinero"],
        plan=["transfer_money"],
        tasks=[Task(task="transfer_money", type="user_task")],
        user_tasks=[UserTask(task="transfer_money", type="user_task")],
        capabilities=["transfer.create"],
        concepts=["Transfer"],
        explanation="Transfer flow.",
        source="test",
    )
    process_payload = {
        "process_id": "money_transfer",
        "process_name": "Money Transfer",
        "domain": "banking.payments",
        "owner": "Payments",
        "description": "Transfer process.",
        "related_flow_ids": ["money.transfer"],
        "execution_nodes": [
            {
                "node_id": "start",
                "name": "Start",
                "type": "start",
                "implementation": "builtin.start",
                "description": "Start.",
            }
        ],
    }
    assets = OrchestratorAssetRegistry(
        knowledge_base_service=KnowledgeBaseService(FakeKnowledgeBaseRepository([flow])),
        asset_repository=EnterpriseAssetRepository(
            [
                EnterpriseAsset(
                    asset_id="process.money_transfer",
                    asset_type="process",
                    name="Money Transfer",
                    status="approved",
                    payload=process_payload,
                    relations=[AssetRelation(type="implements_flow", target_asset_id="flow.money.transfer")],
                )
            ]
        ),
    ).list_assets()

    assert assets["flows"][0]["flow_id"] == "money.transfer"
    assert assets["processes"][0]["process_id"] == "money_transfer"
    assert assets["links"] == [{"flow_id": "money.transfer", "process_id": "money_transfer"}]
