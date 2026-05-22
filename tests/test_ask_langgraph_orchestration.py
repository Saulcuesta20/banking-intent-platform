from pathlib import Path

from app.approval.policy import AlwaysHumanApprovalPolicy
from app.approval.service import ApprovalService
from app.audit.noop import NoopAuditSink
from app.audit.service import AuditService
from app.capability.service import CapabilityService
from app.flow_context.service import FlowAnswerContextService
from app.intent.service import IntentClassificationService, IntentResolutionService
from app.models import KnowledgeRecord, Task
from app.retrieval.service import KnowledgeRetrievalService


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


class FakeRetrievalProvider:
    def __init__(self, record):
        self.record = record

    def retrieve(self, question: str):
        return [self.record]


class FakeReasoningProvider:
    def classify_intent(self, question: str, records: list[KnowledgeRecord]):
        return records[0]


class FakeCapabilityProvider:
    def find_for_record(self, record: KnowledgeRecord, tasks: list[Task]):
        return []

    def build_action_registry(self, records: list[KnowledgeRecord]):
        return []

    def list_registered_actions(self):
        return []


def test_intent_resolution_uses_langgraph_ask_orchestration(monkeypatch, tmp_path: Path):
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
        ontology_nodes=["Loan"],
        ontology_aliases={"Loan": ["credito", "prestamo"]},
        explanation="Matched refinance flow.",
        source="test",
    )
    service = IntentResolutionService(
        retrieval_service=KnowledgeRetrievalService(FakeRetrievalProvider(record)),
        classification_service=IntentClassificationService(FakeReasoningProvider()),
        capability_service=CapabilityService(FakeCapabilityProvider()),
        flow_context_service=FlowAnswerContextService(),
        approval_service=ApprovalService(AlwaysHumanApprovalPolicy()),
        audit_service=AuditService(NoopAuditSink()),
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
    assert ("orchestration", "workflow=langgraph_ask") in trace_events
