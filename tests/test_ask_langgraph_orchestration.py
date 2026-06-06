import json
from pathlib import Path

from app.approval.policy import AlwaysHumanApprovalPolicy
from app.approval.service import ApprovalService
from app.audit.noop import NoopAuditSink
from app.audit.service import AuditService
from app.knowledge_base.models import AssetSearchResult, EnterpriseAsset
from app.ask.answer import AnswerBuilder
from app.ask.intent import FlowSelectionService
from app.ask.service import AskService
from app.ask.understanding import QuestionUnderstanding
from app.capability.service import CapabilityService
from app.knowledge_base.service import KnowledgeBaseService
from app.models import KnowledgeRecord, Task


class FakeCompiledGraph:
    def __init__(self, builder):
        self.builder = builder

    def invoke(self, state):
        current = self.builder.start
        while current != "__end__":
            update = self.builder.nodes[current](state)
            state.update(update)
            route = self.builder.conditional_edges.get(current)
            if route:
                route_value = route["path"](state)
                current = route["path_map"][route_value]
            else:
                current = self.builder.edges[current]
        return state


class FakeStateGraph:
    def __init__(self, state_schema):
        self.state_schema = state_schema
        self.nodes = {}
        self.edges = {}
        self.conditional_edges = {}
        self.start = None

    def add_node(self, name, action):
        self.nodes[name] = action

    def add_edge(self, source, target):
        if source == "__start__":
            self.start = target
        else:
            self.edges[source] = target

    def add_conditional_edges(self, source, path, path_map):
        self.conditional_edges[source] = {"path": path, "path_map": path_map}

    def compile(self):
        return FakeCompiledGraph(self)


class FakeGraphModule:
    StateGraph = FakeStateGraph
    START = "__start__"
    END = "__end__"


class FakeKnowledgeBaseRepository:
    def __init__(self, record):
        self.record = record

    def search(self, search_terms: list[str]):
        return [self.record]

    def upsert_record(self, record: KnowledgeRecord):
        return None


class FakeReasoningProvider:
    def select_intent(self, question: str, records: list[KnowledgeRecord]):
        return records[0]


class FakeQuestionUnderstandingService:
    def understand(self, question: str):
        return QuestionUnderstanding(original_question=question, search_terms=["credito"], entities=["Loan"])


class FakeCapabilityProvider:
    def find_for_record(self, record: KnowledgeRecord, tasks: list[Task]):
        return []

    def build_action_registry(self, records: list[KnowledgeRecord]):
        return []

    def list_registered_actions(self):
        return []


class FakeAssetSearchService:
    def search(self, query: str):
        return AssetSearchResult(
            query=query,
            primary_assets=[
                EnterpriseAsset(
                    asset_id="qa.automatic_payment_account_required",
                    asset_type="qa",
                )
            ],
            supporting_assets=[
                EnterpriseAsset(
                    asset_id="business_rule.automatic_payment_account_required",
                    asset_type="business_rule",
                )
            ],
            evidence_assets=[
                EnterpriseAsset(
                    asset_id="plan.savings_account_opening",
                    asset_type="plan",
                )
            ],
        )


def test_ask_service_uses_langgraph_orchestration(monkeypatch, tmp_path: Path):
    record = KnowledgeRecord(
        flow_id="loan.refinance",
        flow_name="Loan Refinance",
        intent="loan.refinance",
        confidence=0.9,
        business_event="LoanRefinancingRequested",
        utterances=["quiero refinanciar mi credito"],
        plan=["review_refinance_options"],
        tasks=[Task(task="review_refinance_options", type="user_task")],
        capabilities=[],
        concepts=["Loan"],
        concept_aliases={"Loan": ["credito", "prestamo"]},
        explanation="Matched refinance flow.",
        source="test",
    )
    service = AskService(
        knowledge_base_service=KnowledgeBaseService(FakeKnowledgeBaseRepository(record)),
        question_understanding_service=FakeQuestionUnderstandingService(),
        flow_selection_service=FlowSelectionService(FakeReasoningProvider()),
        capability_service=CapabilityService(FakeCapabilityProvider()),
        answer_builder=AnswerBuilder(),
        approval_service=ApprovalService(AlwaysHumanApprovalPolicy()),
        audit_service=AuditService(NoopAuditSink()),
        asset_search_service=FakeAssetSearchService(),
        trace_directory=tmp_path,
        use_langgraph_orchestration=True,
    )
    monkeypatch.setattr(
        service,
        "_optional_import",
        lambda module_name, friendly_name=None: FakeGraphModule,
    )
    trace_events = []

    result = service.resolve(
        "Quiero refinanciar mi credito",
        lambda component, message: trace_events.append((component, message)),
    )

    assert result.flow_id == "loan.refinance"
    assert result.to_dict()["can_resolve"] is True
    assert result.to_dict()["related_concepts"] == ["Loan"]
    assert ("orchestration", "workflow=langgraph_ask") in trace_events
    assert any(component == "question_understanding" for component, _ in trace_events)
    assert any(component == "asset_search" for component, _ in trace_events)
    assert any(component == "knowledge_source_router" for component, _ in trace_events)
    assert any(component == "evidence_bundle" for component, _ in trace_events)
    trace_file = next(tmp_path.glob("ask_trace_*.json"))
    payload = json.loads(trace_file.read_text(encoding="utf-8"))
    assert payload["asset_search"]["primary_assets"] == ["qa.automatic_payment_account_required"]
    assert "process_flows" in [route["source"] for route in payload["evidence_bundle"]["routes"]]
    assert "entities" in [route["source"] for route in payload["evidence_bundle"]["routes"]]
    assert payload["evidence_bundle"]["evidence"][0]["asset_id"] == "loan.refinance"
