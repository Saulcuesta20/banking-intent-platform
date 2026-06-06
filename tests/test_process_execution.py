from app.knowledge_base.models import AssetRelation, EnterpriseAsset
from app.knowledge_base.repository import EnterpriseAssetRepository
from app.orchestrator.orchestration_executor import OrchestrationExecutionRequest, OrchestrationExecutorService
from app.orchestrator.node_policy import ExecutionNodePolicy, NodePolicyError
from app.orchestrator.node_definition import NodeDefinitionModel


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

def process_repository(*extra_assets: EnterpriseAsset) -> EnterpriseAssetRepository:
    return EnterpriseAssetRepository(
        [
            EnterpriseAsset(
                asset_id="process.loan.application",
                asset_type="process",
                name="Loan Application",
                status="approved",
                payload=process_payload(),
                relations=[
                    AssetRelation(type="implements_flow", target_asset_id="flow.loan_application_process")
                ],
            ),
            *extra_assets,
        ]
    )


def test_process_execution_waits_for_user_input():
    service = OrchestrationExecutorService(asset_repository=process_repository())

    result = service.execute(
        OrchestrationExecutionRequest(flow_id="loan_application_process", use_langgraph=False)
    )

    assert result.status == "waiting_for_user_input"
    assert result.current_node_id == "wait_for_data"
    assert result.waiting_for == ["customer_id", "loan_amount"]
    assert result.workflow_trace[0]["event"] == "workflow_compile"
    assert any(item["event"] == "node_waiting" for item in result.workflow_trace)


def test_process_execution_resumes_and_invokes_protocol_integrations():
    service = OrchestrationExecutorService(asset_repository=process_repository())

    result = service.execute(
        OrchestrationExecutionRequest(
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
    assert any(item["event"] == "route_decision" for item in result.workflow_trace)


def test_process_execution_applies_business_rule_gate():
    repository = process_repository(
        EnterpriseAsset(
            asset_id="business_rule.loan_application_gate",
            asset_type="business_rule",
            name="Loan Application Gate",
            relations=[
                AssetRelation(type="applies_to_flow", target_asset_id="flow.loan_application_process")
            ],
            payload={
                "gate": {
                    "applies_before_execution": True,
                    "required_data": ["customer_id"],
                }
            },
        )
    )

    service = OrchestrationExecutorService(asset_repository=repository)

    result = service.execute(
        OrchestrationExecutionRequest(flow_id="loan_application_process", use_langgraph=False)
    )

    assert result.status == "waiting_for_user_input"
    assert result.current_node_id == "start"
    assert result.waiting_for == ["customer_id"]
    assert result.events[0].node_id == "rule_gate"
    assert result.workflow_trace[0]["event"] == "rule_gate_check"


def test_process_execution_loads_flow_definition_from_graph_asset():
    payload = {
        "process_id": "loan_refinance",
        "process_name": "Loan Refinance",
        "status": "approved",
        "domain": "banking.loans",
        "owner": "Credit Operations",
        "description": "Refinance a loan.",
        "related_flow_ids": ["loan_refinance"],
        "execution_nodes": [
            {
                "node_id": "start",
                "name": "Start",
                "type": "start",
                "implementation": "builtin.start",
                "description": "Start.",
            },
            {
                "node_id": "collect_data",
                "name": "Collect Data",
                "type": "user_task",
                "node_kind": "user_task",
                "implementation": "task.collect",
                "description": "Collect user data.",
                "related_user_task_id": "review_refinance_options",
                "required_inputs": ["customer_id"],
            },
            {
                "node_id": "finish",
                "name": "Finish",
                "type": "end",
                "implementation": "builtin.end",
                "description": "End.",
            },
        ],
        "transitions": [
            {"from_node": "start", "to_node": "collect_data"},
            {"from_node": "collect_data", "to_node": "finish"},
        ],
    }
    service = OrchestrationExecutorService(
        asset_repository=EnterpriseAssetRepository(
            [
                EnterpriseAsset(
                    asset_id="process.loan_refinance",
                    asset_type="process",
                    status="approved",
                    payload=payload,
                )
            ]
        )
    )
    result = service.execute(
        OrchestrationExecutionRequest(
            flow_id="loan_refinance",
            data={"customer_id": "C-1"},
            use_langgraph=False,
        )
    )
    assert result.status == "completed"
    assert result.instance_id is not None


def test_process_execution_rejects_graph_flow_with_disallowed_node_type():
    payload = {
        "process_id": "loan_refinance",
        "process_name": "Loan Refinance",
        "status": "approved",
        "domain": "banking.loans",
        "owner": "Credit Operations",
        "description": "Refinance a loan.",
        "related_flow_ids": ["loan_refinance"],
        "execution_nodes": [
            {
                "node_id": "start",
                "name": "Start",
                "type": "start",
                "implementation": "builtin.start",
                "description": "Start.",
            },
            {
                "node_id": "custom_script",
                "name": "Custom Script",
                "type": "service_call",
                "implementation": "custom.script",
                "description": "Disallowed node by policy.",
            },
        ],
    }
    service = OrchestrationExecutorService(
        asset_repository=EnterpriseAssetRepository(
            [
                EnterpriseAsset(
                    asset_id="process.loan_refinance",
                    asset_type="process",
                    status="approved",
                    payload=payload,
                )
            ]
        ),
        node_definition_model=NodeDefinitionModel(
            policy=ExecutionNodePolicy(
                allowed_types={
                    "flow": {"start", "end"},
                    "process": {"start", "end"},
                }
            )
        ),
    )
    try:
        service.execute(OrchestrationExecutionRequest(flow_id="loan_refinance", use_langgraph=False))
        assert False, "Expected NodePolicyError"
    except NodePolicyError as exc:
        assert "unsupported node types" in str(exc)
