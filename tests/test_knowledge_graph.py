import json
from pathlib import Path

from app.ingestion.flow_loader import FileKnowledgeIngestionProvider
from app.knowledge_graph.neo4j import Neo4jKnowledgeGraphRepository
from app.knowledge_graph.service import KnowledgeGraphService
from app.models import Action, KnowledgeRecord, Task, UserTask


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
    query = Neo4jKnowledgeGraphRepository.FILTERED_GRAPH_CONTEXT_QUERY

    assert ":Concept" in query
    assert ":RELATES_TO" in query
    assert ":Ontology" not in query


def test_upsert_record_persists_concepts_tasks_actions_and_synonyms():
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
                front_actions=[Action(action="ui.refinance.submit", type="front_action")],
                back_actions=[Action(action="loan.calculate", type="back_action")],
            )
        ],
        capabilities=["loan.calculate"],
        concepts=["Loan"],
        concept_aliases={"Loan": ["prestamo"]},
        explanation="Matched refinance flow.",
        source="test",
    )
    tx = CapturingTransaction()

    Neo4jKnowledgeGraphRepository._upsert_record(tx, record)

    statements = "\n".join(tx.queries)
    assert "MERGE (c:Concept {name: $concept})" in statements
    assert "MERGE (f)-[:RELATES_TO]->(c)" in statements
    assert "MERGE (c)-[:HAS_SYNONYM]->(s)" in statements
    assert "MERGE (f)-[rel:HAS_USER_TASK]->(t)" in statements
    assert "HAS_FRONT_ACTION" in statements
    assert "HAS_BACK_ACTION" in statements


def test_clear_graph_removes_legacy_ontology_nodes_during_migration():
    tx = CapturingTransaction()

    Neo4jKnowledgeGraphRepository._clear_graph(tx)

    assert "n:Concept" in tx.queries[0]
    assert "n:Ontology" in tx.queries[0]


def test_ingestion_persists_flow_artifacts_through_knowledge_graph(tmp_path: Path):
    flow_dir = tmp_path / "flows"
    flow_dir.mkdir()
    (flow_dir / "loan.flow.json").write_text(
        json.dumps(
            {
                "flow_id": "loan.request",
                "flow_name": "Loan Request",
                "intent": "loan.request",
                "business_event": "LoanRequested",
                "utterances": ["quiero un prestamo"],
                "plan": [],
                "capabilities": [],
                "concepts": ["Loan"],
                "concept_aliases": {"Loan": ["prestamo"]},
                "explanation": "Loan request.",
            }
        ),
        encoding="utf-8",
    )
    repository = CapturingRepository()
    provider = FileKnowledgeIngestionProvider(
        flow_directory=flow_dir,
        processed_directory=tmp_path / "processed",
        knowledge_graph_service=KnowledgeGraphService(repository),
    )

    records = provider.ingest(flow_dir)

    assert repository.initialized is True
    assert [record.flow_id for record in repository.records] == ["loan.request"]
    assert records[0].concepts == ["Loan"]
