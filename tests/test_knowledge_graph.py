from app.knowledge_base.adapters.graph.neo4j import Neo4jKnowledgeBaseGraphAdapter
from app.knowledge_base.service import KnowledgeBaseService
from app.knowledge_base.source_router import KnowledgeSourceRouter
from app.models import KnowledgeRecord, Task, UserTask
from app.tools.models import ToolDefinition


class CapturingTransaction:
    def __init__(self):
        self.queries: list[str] = []

    def run(self, query: str, parameters=None):
        self.queries.append(" ".join(query.split()))


class CapturingRepository:
    def __init__(self):
        self.initialized = False
        self.records: list[KnowledgeRecord] = []

    def initialize(self):
        self.initialized = True

    def upsert_record(self, record: KnowledgeRecord):
        self.records.append(record)

    def search(self, search_terms: list[str]):
        return []


def test_neo4j_queries_use_concepts_as_the_knowledge_vocabulary():
    query = Neo4jKnowledgeBaseGraphAdapter.FILTERED_GRAPH_CONTEXT_QUERY

    assert ":Concept" in query
    assert ":RELATES_TO" in query
    assert ":Ontology" not in query


def test_upsert_record_persists_concepts_tasks_tools_and_synonyms():
    record = KnowledgeRecord(
        flow_id="loan.refinance",
        flow_name="Loan Refinance",
        intent="loan.refinance",
        confidence=0.9,
        business_event="LoanRefinancingRequested",
        utterances=["quiero refinanciar mi credito"],
        plan=["review_options"],
        tasks=[Task(task="review_options", type="user_task")],
        user_tasks=[
            UserTask(
                task="review_options",
                type="user_task",
                tools=[
                    ToolDefinition(tool_id="ui.refinance.submit", tool_type="frontend_tool"),
                    ToolDefinition(tool_id="loan.calculate", tool_type="backend_tool"),
                ],
            )
        ],
        capabilities=["loan.calculate"],
        concepts=["Loan"],
        concept_aliases={"Loan": ["prestamo"]},
        explanation="Matched refinance flow.",
        source="test",
    )
    tx = CapturingTransaction()

    Neo4jKnowledgeBaseGraphAdapter._upsert_record(tx, record)

    statements = "\n".join(tx.queries)
    assert "MERGE (c:Concept {name: $concept})" in statements
    assert "MERGE (f)-[:RELATES_TO]->(c)" in statements
    assert "MERGE (c)-[:HAS_SYNONYM]->(s)" in statements
    assert "MERGE (f)-[rel:HAS_USER_TASK]->(t)" in statements
    assert "MERGE (tool:Tool {tool_id: $tool_id})" in statements
    assert "USES_TOOL" in statements


def test_clear_graph_removes_all_nodes_except_dimensions():
    tx = CapturingTransaction()

    Neo4jKnowledgeBaseGraphAdapter._clear_graph(tx)

    # New approach: delete everything EXCEPT dimension nodes
    assert "NOT n:KnowledgeBase" in tx.queries[0]
    assert "NOT n:Engine" in tx.queries[0]
    assert "NOT n:StructuralLayer" in tx.queries[0]
    assert "DETACH DELETE n" in tx.queries[0]


def test_graph_context_text_serializes_structured_user_tasks_consistently():
    row = {
        "flow_id": "loan.refinance",
        "flow_name": "Loan Refinance",
        "intent": "loan.refinance",
        "business_event": "LoanRefinancingRequested",
        "utterances": ["quiero refinanciar mi credito"],
        "concepts": ["Loan"],
        "concept_aliases": ["prestamo"],
        "user_tasks": [
            {"task": "review_refinance_options", "type": "user_task", "order_index": 1},
            {"task": "confirm_refinance_terms", "type": "user_task", "order_index": 2},
        ],
        "tools": ["loan.refinance.calculate"],
        "explanation": "Matched refinance flow.",
    }

    context = Neo4jKnowledgeBaseGraphAdapter._context_text(row)

    assert "user_tasks: review_refinance_options type=user_task" in context
    assert "confirm_refinance_terms type=user_task" in context
    assert "tools: loan.refinance.calculate" in context


def test_ingestion_persists_flow_records_through_knowledge_base():
    record = KnowledgeRecord(
        flow_id="loan.request",
        flow_name="Loan Request",
        intent="loan.request",
        confidence=0.8,
        business_event="LoanRequested",
        utterances=["quiero un prestamo"],
        plan=[],
        tasks=[],
        user_tasks=[],
        capabilities=[],
        concepts=["Loan"],
        concept_aliases={"Loan": ["prestamo"]},
        explanation="Loan request.",
        source="test",
    )
    repository = CapturingRepository()
    KnowledgeBaseService(repository).ingest([record])

    assert repository.initialized is True
    assert [record.flow_id for record in repository.records] == ["loan.request"]


def test_knowledge_source_router_selects_sources_without_replacing_goal_routing():
    router = KnowledgeSourceRouter()

    routes = router.route(
        question="Quiero refinanciar mi prestamo y saber si hay una regla de pago automatico",
        search_terms=["prestamo", "refinanciar"],
        question_understanding={
            "routing_hints": {
                "needs_answer": True,
                "needs_flow": True,
                "needs_process": False,
                "needs_tool_explanation": False,
            }
        },
        asset_search={
            "enabled": True,
            "primary_assets": ["qa.automatic_payment_account_required"],
            "supporting_assets": ["business_rule.automatic_payment_account_required"],
        },
    )

    assert [route.source for route in routes] == ["qa", "process_flows", "rules_policies", "entities"]
    assert routes[0].views == ["repository", "vector"]
    assert routes[2].views == ["repository", "document", "graph"]
    assert routes[3].views == ["graph", "repository"]
