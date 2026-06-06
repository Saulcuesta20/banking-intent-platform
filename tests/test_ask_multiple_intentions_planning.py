from app.approval.policy import AlwaysHumanApprovalPolicy
from app.approval.service import ApprovalService
from app.audit.noop import NoopAuditSink
from app.audit.service import AuditService
from app.ask.answer import AnswerBuilder
from app.ask.intent import FlowSelectionService
from app.ask.service import AskService
from app.ask.understanding import QuestionUnderstanding
from app.capability.registry import RegistryCapabilityProvider
from app.capability.service import CapabilityService
from app.knowledge_base.service import KnowledgeBaseService
from app.models import KnowledgeRecord
from app.planning.service import PlanningService
from conftest import sample_records


class FakeKnowledgeBaseRepository:
    def __init__(self, records: list[KnowledgeRecord]):
        self.records = records

    def search(self, search_terms: list[str]):
        return self.records

    def upsert_record(self, record: KnowledgeRecord):
        return None


class FakeLLMReasoningProvider:
    def __init__(self, selected_flow_id: str | None):
        self.selected_flow_id = selected_flow_id

    def select_intent(self, question: str, records: list[KnowledgeRecord]):
        if self.selected_flow_id is None:
            return None
        for record in records:
            if record.flow_id == self.selected_flow_id:
                return record
        return None


class FakeQuestionUnderstandingService:
    def understand(self, question: str):
        return QuestionUnderstanding(original_question=question, search_terms=question.lower().split())


def load_records(*flow_ids):
    return sample_records(*flow_ids)


def test_ask_result_contains_goal_user_needs_route_and_multiple_intentions_plan():
    records = load_records("loan.refinance", "savings_account_opening", "loan.payment")
    capability_service = CapabilityService(RegistryCapabilityProvider(records))
    service = AskService(
        knowledge_base_service=KnowledgeBaseService(FakeKnowledgeBaseRepository(records)),
        question_understanding_service=FakeQuestionUnderstandingService(),
        flow_selection_service=FlowSelectionService(FakeLLMReasoningProvider("loan.refinance")),
        capability_service=capability_service,
        answer_builder=AnswerBuilder(),
        approval_service=ApprovalService(AlwaysHumanApprovalPolicy()),
        audit_service=AuditService(NoopAuditSink()),
        planning_service=PlanningService(),
        use_langgraph_orchestration=False,
    )

    result = service.resolve(
        "Quiero refinanciar mi prestamo para bajar la cuota, explicame como calculan "
        "las condiciones y dime si necesito abrir una cuenta para pago automatico"
    )
    payload = result.to_dict()

    assert payload["goal"]["type"] == "business_goal"
    assert payload["route"]["mode"] == "multiple_intentions"
    assert {need["resolution_action"] for need in payload["user_needs"]} >= {
        "invoke_known_flow",
        "explain_tool",
        "answer_question",
    }
    assert payload["multiple_intentions_plan"]["planning_mode"] == "multiple_intentions"
    assert any(step["tools"] for step in payload["multiple_intentions_plan"]["steps"])
    assert payload["requires_execution_confirmation"] is True
    assert payload["execution_selection_policy"]["path"] == "multiple_intentions_route"
    assert payload["execution_selection_policy"]["selection_mode"] == "multiple"
    assert payload["execution_options"][0]["option_id"] == "continue_multiple_intentions_plan"
    assert all(option["executes_tools_now"] is False for option in payload["execution_options"])
