from pathlib import Path

import pytest

from app.approval.policy import AlwaysHumanApprovalPolicy
from app.approval.service import ApprovalService
from app.audit.noop import NoopAuditSink
from app.audit.service import AuditService
from app.capability.registry import RegistryCapabilityProvider
from app.capability.service import CapabilityService
from app.factory import build_intent_service
from app.flow_context.service import FlowAnswerContextService
from app.ingestion.flow_loader import FlowKnowledgeLoader
from app.intent.service import IntentClassificationService, IntentResolutionService
from app.models import KnowledgeRecord
from app.retrieval.service import KnowledgeRetrievalService


FLOW_DIR = Path(__file__).resolve().parents[1] / "data" / "flows"


class FakeGraphRetrievalProvider:
    def __init__(self, records: list[KnowledgeRecord]):
        self.records = records

    def retrieve(self, question: str):
        return self.records


class FakeLLMReasoningProvider:
    def __init__(self, selected_flow_id: str | None):
        self.selected_flow_id = selected_flow_id

    def classify_intent(self, question: str, records: list[KnowledgeRecord]):
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


def build_test_service(records: list[KnowledgeRecord], selected_flow_id: str | None):
    startup_records = FlowKnowledgeLoader().load_directory(FLOW_DIR)
    return IntentResolutionService(
        retrieval_service=KnowledgeRetrievalService(FakeGraphRetrievalProvider(records)),
        classification_service=IntentClassificationService(FakeLLMReasoningProvider(selected_flow_id)),
        capability_service=CapabilityService(RegistryCapabilityProvider(startup_records)),
        flow_context_service=FlowAnswerContextService(),
        approval_service=ApprovalService(AlwaysHumanApprovalPolicy()),
        audit_service=AuditService(NoopAuditSink()),
        use_langgraph_orchestration=False,
    )


def load_record(flow_id: str) -> KnowledgeRecord:
    records = FlowKnowledgeLoader().load_directory(FLOW_DIR)
    for record in records:
        if record.flow_id == flow_id:
            return record
    raise AssertionError(f"Missing flow fixture {flow_id}")


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


def test_ambiguous_question_returns_unknown_when_llm_declines_flow():
    records = [load_record("loan.request"), load_record("money.transfer")]
    result = build_test_service(records, None).resolve("No tengo dinero que haog")

    assert result.to_dict()["can_resolve"] is False
    assert result.intent == "unknown"
    assert result.confidence == 0.0


def test_factory_rejects_non_ai_ask_flow(monkeypatch):
    monkeypatch.setenv("USE_AI_PROVIDERS", "false")

    with pytest.raises(RuntimeError, match="USE_AI_PROVIDERS must be true"):
        build_intent_service()
