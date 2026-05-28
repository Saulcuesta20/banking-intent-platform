import json
from pathlib import Path

from app.ingestion.flow_loader import FileKnowledgeIngestionProvider
from app.ingestion.process_loader import ProcessDefinitionLoader


def process_payload():
    return {
        "process_id": "customer.onboarding",
        "process_name": "Customer Onboarding",
        "version": "1.0.0",
        "status": "draft",
        "domain": "banking.customer",
        "owner": "Customer Operations",
        "description": "Create and validate a customer onboarding case.",
        "related_flow_ids": ["customer.onboarding"],
        "triggers": ["alta de cliente"],
        "inputs": ["customer_documents"],
        "outputs": ["customer_profile"],
        "actors": [
            {
                "actor_id": "customer",
                "name": "Customer",
                "role": "Provides onboarding data.",
                "type": "customer",
            }
        ],
        "systems": [
            {
                "system_id": "onboarding",
                "name": "Customer Onboarding",
                "type": "internal",
                "owner": "Customer Operations",
            }
        ],
        "documents": [
            {
                "document_id": "identity_document",
                "name": "Identity Document",
                "required": True,
                "source": "customer",
            }
        ],
        "rules": [
            {
                "rule_id": "documents_required",
                "description": "Identity documents are required.",
                "severity": "high",
            }
        ],
        "decisions": [
            {
                "decision_id": "kyc_result",
                "question": "Did the customer pass KYC?",
                "outcomes": ["approved", "manual_review"],
            }
        ],
        "exceptions": [
            {
                "exception_id": "missing_documents",
                "condition": "Documents are missing.",
                "resolution": "Ask for corrected documents.",
            }
        ],
        "steps": [
            {
                "step_id": "start",
                "sequence": 1,
                "name": "Start Onboarding",
                "type": "start",
                "actor_id": "customer",
                "system_id": "onboarding",
                "description": "Start the onboarding process.",
                "related_user_task_id": "handle_customer_onboarding",
                "executable": True,
                "actions": ["customer.create"],
                "execution_node_ids": ["start"],
            }
        ],
        "metadata": {"schema": "process_definition.v1"},
    }


def test_process_definition_loader_loads_fixed_process_json(tmp_path: Path):
    process_dir = tmp_path / "processes"
    process_dir.mkdir()
    (process_dir / "customer_onboarding.process.json").write_text(
        json.dumps(process_payload()),
        encoding="utf-8",
    )

    processes = ProcessDefinitionLoader().load_directory(process_dir)

    assert [process.process_id for process in processes] == ["customer.onboarding"]
    assert processes[0].steps[0].related_user_task_id == "handle_customer_onboarding"
    assert processes[0].steps[0].execution_node_ids == ["start"]
    assert processes[0].rules[0].severity == "high"


def test_ingestion_index_includes_process_definitions(tmp_path: Path):
    flow_dir = tmp_path / "flows"
    flow_dir.mkdir()
    (flow_dir / "customer_onboarding.flow.json").write_text(
        json.dumps(
            {
                "flow_id": "customer.onboarding",
                "flow_name": "Customer Onboarding",
                "intent": "customer.onboarding",
                "business_event": "CustomerOnboardingRequested",
                "utterances": ["alta de cliente"],
                "plan": [],
                "capabilities": [],
                "concepts": ["Customer"],
                "explanation": "Customer onboarding.",
            }
        ),
        encoding="utf-8",
    )
    process_dir = tmp_path / "processes"
    process_dir.mkdir()
    (process_dir / "customer_onboarding.process.json").write_text(
        json.dumps(process_payload()),
        encoding="utf-8",
    )

    provider = FileKnowledgeIngestionProvider(
        flow_directory=flow_dir,
        process_directory=process_dir,
        processed_directory=tmp_path / "processed",
    )

    provider.ingest(flow_dir)

    index = json.loads((tmp_path / "processed" / "knowledge_index.json").read_text(encoding="utf-8"))
    assert index["processes"][0]["process_id"] == "customer.onboarding"
    assert index["processes"][0]["steps"][0]["step_id"] == "start"
