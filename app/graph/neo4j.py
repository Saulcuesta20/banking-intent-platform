from __future__ import annotations

from typing import Any

from app.graph.providers import GraphRepository
from app.models import KnowledgeRecord


def _optional_import(module_name: str, friendly_name: str | None = None):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Optional dependency '{friendly_name or module_name}' is required for this provider."
        ) from exc


class Neo4jGraphRepository(GraphRepository):
    def __init__(self, uri: str, user: str, password: str):
        neo4j = _optional_import("neo4j")
        self.driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))

    def upsert_record(self, record: KnowledgeRecord) -> None:
        with self.driver.session() as session:
            session.execute_write(self._create_record, record)

    @staticmethod
    def _create_record(tx: Any, record: KnowledgeRecord) -> None:
        tx.run(
            "MERGE (f:Flow {flow_id: $flow_id}) "
            "SET f.intent = $intent, f.business_event = $business_event, "
            "f.capabilities = $capabilities, f.ontology_nodes = $ontology_nodes",
            {
                "flow_id": record.flow_id,
                "intent": record.intent,
                "business_event": record.business_event,
                "capabilities": record.capabilities,
                "ontology_nodes": record.ontology_nodes,
            },
        )

    def find_related(self, intent: str) -> dict[str, list[str]]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (f:Flow {intent: $intent})--(related) "
                "RETURN labels(related) AS labels, coalesce(related.name, related.task, related.action, related.text) AS name",
                {"intent": intent},
            )
            related: dict[str, list[str]] = {}
            for record in result:
                label = record["labels"][0] if record["labels"] else "Related"
                related.setdefault(label, []).append(record["name"])
            return related
