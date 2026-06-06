import pytest

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
from app.factory import build_ask_service
from app.knowledge_base.service import KnowledgeBaseService
from app.models import KnowledgeRecord
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
                return record.model_copy(
                    update={
                        "metadata": {
                            **record.metadata,
                            "reasoning_provider": "fake_llm_reasoning",
                            "llm_answer": {
                                "can_resolve": True,
                                "selected_flow_id": record.flow_id,
                                "confidence": record.confidence,
                            },
                            "llm_reason": "Fake LLM selected the graph candidate.",
                        }
                    }
                )
        return None


class FakeQuestionUnderstandingService:
    def understand(self, question: str):
        return QuestionUnderstanding(original_question=question, search_terms=question.lower().split())


def build_test_service(records: list[KnowledgeRecord], selected_flow_id: str | None):
    return AskService(
        knowledge_base_service=KnowledgeBaseService(FakeKnowledgeBaseRepository(records)),
        question_understanding_service=FakeQuestionUnderstandingService(),
        flow_selection_service=FlowSelectionService(FakeLLMReasoningProvider(selected_flow_id)),
        capability_service=CapabilityService(RegistryCapabilityProvider(records)),
        answer_builder=AnswerBuilder(),
        approval_service=ApprovalService(AlwaysHumanApprovalPolicy()),
        audit_service=AuditService(NoopAuditSink()),
        use_langgraph_orchestration=False,
    )


def load_record(flow_id: str) -> KnowledgeRecord:
    return sample_records(flow_id)[0]


def test_refinance_question_projects_llm_selected_graph_flow():
    record = load_record("loan.refinance")
    result = build_test_service([record], "loan.refinance").resolve("Quiero refinanciar mi prestamo")

    assert result.intent == "loan.refinance"
    assert result.flow_id == "loan.refinance"
    assert result.confidence == 0.9
    assert result.business_event == "LoanRefinancingRequested"
    assert result.requires_human_approval is True
    assert result.plan == [
        "identify_customer",
        "review_loan_status",
        "review_refinance_options",
        "prepare_refinance_request",
        "approve_business_case",
    ]
    assert result.requires_execution_confirmation is True
    assert result.execution_selection_policy["path"] == "flow_route"
    assert result.execution_selection_policy["selection_mode"] == "single"
    assert result.execution_options
    assert all(option["executes_tools_now"] is False for option in result.execution_options)


def test_ambiguous_question_returns_unknown_when_llm_declines_flow():
    records = [load_record("loan.request"), load_record("money.transfer")]
    result = build_test_service(records, None).resolve("No tengo dinero que haog")

    assert result.to_dict()["can_resolve"] is False
    assert result.intent == "unknown"
    assert result.confidence == 0.0


def test_direct_qa_question_resolves_without_flow_clarification():
    records = [load_record("savings_account_opening"), load_record("loan.payment")]
    result = build_test_service(records, None).resolve("Necesito una cuenta para pago automatico?")

    assert result.to_dict()["can_resolve"] is True
    assert result.intent == "qa.answer"
    assert result.requires_human_approval is False
    assert result.requires_execution_confirmation is False
    assert result.execution_selection_policy["path"] == "qa_route"
    assert result.execution_selection_policy["selection_mode"] == "none"
    assert result.route["mode"] == "known_route"
    assert result.plan == []


def test_factory_rejects_non_ai_ask_flow(monkeypatch):
    monkeypatch.setenv("USE_AI_PROVIDERS", "false")

    with pytest.raises(RuntimeError, match="USE_AI_PROVIDERS must be true"):
        build_ask_service()
