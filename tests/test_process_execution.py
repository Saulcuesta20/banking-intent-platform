import json
from pathlib import Path

from app.orchestrator.process_execution import ProcessExecutionRequest, ProcessExecutionService


def write_flow(flow_dir: Path) -> None:
    flow_dir.mkdir()
    (flow_dir / "loan_application_process.flow.json").write_text(
        json.dumps(
            {
                "flow_id": "loan_application_process",
                "flow_name": "Loan Application Process",
                "intent": "loan.application.submit",
                "business_event": "LoanApplied",
                "utterances": ["quiero solicitar un prestamo"],
                "plan": ["apply_for_loan"],
                "user_task_refs": ["apply_for_loan"],
                "capabilities": ["loan.application.create"],
                "concepts": ["Loan"],
                "explanation": "Loan application flow.",
            }
        ),
        encoding="utf-8",
    )


def process_payload():
    return {
        "process_id": "loan.application",
        "process_name": "Loan Application",
        "version": "1.0.0",
        "status": "draft",
        "domain": "banking.loans",
        "owner": "Credit Operations",
        "description": "Loan application process.",
        "related_flow_ids": ["loan_application_process"],
        "triggers": ["quiero solicitar un prestamo"],
        "inputs": ["customer_id", "loan_amount"],
        "outputs": ["loan_application_id"],
        "integrations": [
            {
                "integration_id": "loan_origination_create",
                "name": "Create Loan Application",
                "type": "legacy_service",
                "protocol": "api",
                "operation": "create",
                "endpoint": "loan.application.create",
            },
            {
                "integration_id": "loan_scoring_grpc",
                "name": "Evaluate Loan Scoring",
                "type": "legacy_service",
                "protocol": "grpc",
                "operation": "calculate",
                "endpoint": "LoanScoringService/Evaluate",
            },
        ],
        "activities": [
            {
                "activity_id": "capture_loan_use_case",
                "name": "Capture Loan Use Case",
                "type": "use_case",
                "description": "Collect loan data.",
                "execution_node_ids": ["start", "wait_for_data", "create_application"],
            }
        ],
        "execution_nodes": [
            {
                "node_id": "start",
                "name": "Start",
                "type": "start",
                "implementation": "builtin.start",
                "description": "Start process.",
            },
            {
                "node_id": "wait_for_data",
                "name": "Wait For Data",
                "type": "wait_for_user_input",
                "implementation": "builtin.wait_for_user_input",
                "description": "Wait for user data.",
                "required_inputs": ["customer_id", "loan_amount"],
            },
            {
                "node_id": "create_application",
                "name": "Create Application",
                "type": "service_call",
                "implementation": "integration.api",
                "description": "Create application.",
                "integration_id": "loan_origination_create",
            },
            {
                "node_id": "score_application",
                "name": "Score Application",
                "type": "service_call",
                "implementation": "integration.grpc",
                "description": "Score application.",
                "integration_id": "loan_scoring_grpc",
            },
            {
                "node_id": "finish",
                "name": "Finish",
                "type": "end",
                "implementation": "builtin.end",
                "description": "Finish process.",
            },
        ],
        "transitions": [
            {"from_node": "start", "to_node": "wait_for_data"},
            {"from_node": "wait_for_data", "to_node": "create_application", "condition": "required_inputs_present"},
            {"from_node": "create_application", "to_node": "score_application"},
            {"from_node": "score_application", "to_node": "finish"},
        ],
        "steps": [
            {
                "step_id": "capture",
                "sequence": 1,
                "name": "Capture",
                "type": "user_task",
                "description": "Capture data.",
                "executable": True,
                "integrations": ["loan_origination_create"],
                "execution_node_ids": ["start", "wait_for_data", "create_application"],
            }
        ],
    }


def write_process(process_dir: Path) -> None:
    process_dir.mkdir()
    (process_dir / "loan_application.process.json").write_text(
        json.dumps(process_payload()),
        encoding="utf-8",
    )


def test_process_execution_waits_for_user_input(tmp_path: Path):
    flow_dir = tmp_path / "flows"
    process_dir = tmp_path / "processes"
    write_flow(flow_dir)
    write_process(process_dir)

    service = ProcessExecutionService(flow_directory=flow_dir, process_directory=process_dir)

    result = service.execute(
        ProcessExecutionRequest(flow_id="loan_application_process", use_langgraph=False)
    )

    assert result.status == "waiting_for_user_input"
    assert result.current_node_id == "wait_for_data"
    assert result.waiting_for == ["customer_id", "loan_amount"]


def test_process_execution_resumes_and_invokes_protocol_integrations(tmp_path: Path):
    flow_dir = tmp_path / "flows"
    process_dir = tmp_path / "processes"
    write_flow(flow_dir)
    write_process(process_dir)

    service = ProcessExecutionService(flow_directory=flow_dir, process_directory=process_dir)

    result = service.execute(
        ProcessExecutionRequest(
            flow_id="loan_application_process",
            resume_from_node_id="wait_for_data",
            data={"customer_id": "C-123", "loan_amount": 10000},
            use_langgraph=False,
        )
    )

    assert result.status == "completed"
    assert result.data["create_application"]["protocol"] == "api"
    assert result.data["score_application"]["protocol"] == "grpc"
    assert [event.node_id for event in result.events] == [
        "wait_for_data",
        "create_application",
        "score_application",
        "finish",
    ]
