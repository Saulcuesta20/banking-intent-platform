from app.models import ProcessDefinition
from app.orchestrator.service import OrchestratorService


def test_orchestrator_starts_long_running_instance_and_pending_jobs():
    process = ProcessDefinition(
        process_id="loan.application",
        process_name="Loan Application",
        domain="banking.loans",
        owner="Credit Operations",
        description="Loan process.",
        execution_nodes=[
            {
                "node_id": "start",
                "name": "Start",
                "type": "start",
                "implementation": "builtin.start",
                "description": "Start process.",
            }
        ],
        jobs=[
            {
                "job_id": "approval_timer",
                "node_id": "start",
                "type": "timer",
                "status": "pending",
            }
        ],
    )
    orchestrator = OrchestratorService()

    instance = orchestrator.start_process_instance(process, data={"customer_id": "C-123"})
    instance = orchestrator.create_pending_jobs(process, instance)

    assert instance.definition_type == "process"
    assert instance.current_node_id == "start"
    assert instance.pending_jobs[0].type == "timer"
    assert orchestrator.repository.list_pending_jobs()[0].job_id.endswith(":approval_timer")


def test_orchestrator_correlates_message_into_instance_state():
    process = ProcessDefinition(
        process_id="loan.application",
        process_name="Loan Application",
        domain="banking.loans",
        owner="Credit Operations",
        description="Loan process.",
    )
    orchestrator = OrchestratorService()
    instance = orchestrator.start_process_instance(process)

    updated = orchestrator.correlate_message(
        instance.instance_id,
        "LoanApprovalDecisionReceived",
        {"approval_decision": "approved"},
    )

    assert updated.status == "running"
    assert updated.data["approval_decision"] == "approved"
    assert updated.data["_last_message"] == "LoanApprovalDecisionReceived"
