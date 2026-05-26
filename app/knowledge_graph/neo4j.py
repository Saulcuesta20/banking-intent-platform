from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ingestion.flow_loader import FlowKnowledgeLoader
from app.knowledge_graph.providers import KnowledgeGraphRepository
from app.models import KnowledgeRecord


def _optional_import(module_name: str, friendly_name: str | None = None):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Optional dependency '{friendly_name or module_name}' is required for this provider."
        ) from exc


class Neo4jKnowledgeGraphRepository(KnowledgeGraphRepository):
    """Store and search approved banking knowledge in Neo4j."""

    GRAPH_CONTEXT_QUERY = """
        MATCH (f:Flow)
        OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u:Utterance)
        OPTIONAL MATCH (f)-[:RELATES_TO]->(c:Concept)
        OPTIONAL MATCH (c)-[:HAS_SYNONYM]->(s:Synonym)
        OPTIONAL MATCH (f)-[task_rel:HAS_USER_TASK]->(t:UserTask)
        OPTIONAL MATCH (t)-[:HAS_FRONT_ACTION]->(front:Action)
        OPTIONAL MATCH (t)-[:HAS_BACK_ACTION]->(back:Action)
        RETURN
          f.flow_id AS flow_id,
          f.flow_name AS flow_name,
          f.intent AS intent,
          f.business_event AS business_event,
          f.explanation AS explanation,
          collect(DISTINCT u.text) AS utterances,
          collect(DISTINCT c.name) AS concepts,
          collect(DISTINCT s.term) AS concept_aliases,
          collect(DISTINCT t.task) AS user_tasks,
          collect(DISTINCT front.action) AS front_actions,
          collect(DISTINCT back.action) AS back_actions
        ORDER BY flow_id
        """

    FILTERED_GRAPH_CONTEXT_QUERY = """
        MATCH (f:Flow)
        OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u_match:Utterance)
        OPTIONAL MATCH (f)-[:RELATES_TO]->(c_match:Concept)
        OPTIONAL MATCH (c_match)-[:HAS_SYNONYM]->(s_match:Synonym)
        WITH f,
             collect(DISTINCT u_match.text) AS all_utterances,
             collect(DISTINCT c_match.name) AS all_concepts,
             collect(DISTINCT s_match.term) AS all_concept_aliases,
             toLower(
               coalesce(f.flow_id, '') + ' ' +
               coalesce(f.flow_name, '') + ' ' +
               coalesce(f.intent, '') + ' ' +
               coalesce(f.business_event, '') + ' ' +
               coalesce(f.explanation, '') + ' ' +
               reduce(text = '', value IN collect(DISTINCT u_match.text) | text + ' ' + coalesce(value, '')) + ' ' +
               reduce(text = '', value IN collect(DISTINCT c_match.name) | text + ' ' + coalesce(value, '')) + ' ' +
               reduce(text = '', value IN collect(DISTINCT s_match.term) | text + ' ' + coalesce(value, ''))
             ) AS haystack
        WITH f, all_utterances, all_concepts, all_concept_aliases,
             [token IN $tokens WHERE haystack CONTAINS token] AS matched_tokens
        WHERE size(matched_tokens) > 0
        OPTIONAL MATCH (f)-[task_rel:HAS_USER_TASK]->(t:UserTask)
        OPTIONAL MATCH (t)-[:HAS_FRONT_ACTION]->(front:Action)
        OPTIONAL MATCH (t)-[:HAS_BACK_ACTION]->(back:Action)
        RETURN
          f.flow_id AS flow_id,
          f.flow_name AS flow_name,
          f.intent AS intent,
          f.business_event AS business_event,
          f.explanation AS explanation,
          all_utterances AS utterances,
          all_concepts AS concepts,
          all_concept_aliases AS concept_aliases,
          collect(DISTINCT t.task) AS user_tasks,
          collect(DISTINCT front.action) AS front_actions,
          collect(DISTINCT back.action) AS back_actions,
          matched_tokens AS matched_tokens,
          size(matched_tokens) AS match_score
        ORDER BY match_score DESC, flow_id
        LIMIT $limit
        """

    def __init__(
        self,
        flow_directory: Path,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        limit: int = 50,
    ):
        neo4j = _optional_import("neo4j")
        self.driver = neo4j.GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.flow_directory = flow_directory
        self.neo4j_uri = neo4j_uri
        self.records = FlowKnowledgeLoader().load_directory(flow_directory)
        self.records_by_flow_id = {record.flow_id: record for record in self.records}
        self.limit = limit

    def search(self, search_terms: list[str]) -> list[KnowledgeRecord]:
        tokens = search_terms
        graph_rows = self._query_graph_context(tokens)
        if not graph_rows:
            broad_rows = self._query_all_graph_context()
            candidates = []
            for row in broad_rows[: self.limit]:
                record = self.records_by_flow_id.get(row["flow_id"])
                if record is None:
                    continue
                candidates.append(record.model_copy(
                    update={
                        "metadata": {
                            **record.metadata,
                            "knowledge_provider": "neo4j_broad_context",
                            "graph_query_summary": self._query_summary(
                                query=self.GRAPH_CONTEXT_QUERY,
                                row_count=len(broad_rows),
                                tokens=tokens,
                                search_mode="broad_graph_context",
                            ),
                            "graph_rows_preview": self._rows_preview(broad_rows),
                            "graph_context": self._context_text(row),
                        }
                    }
                ))
            return candidates

        candidates = []
        for row in graph_rows:
            flow_id = row["flow_id"]
            record = self.records_by_flow_id.get(flow_id)
            if record is None:
                continue
            candidates.append(
                record.model_copy(
                    update={
                        "metadata": {
                            **record.metadata,
                            "knowledge_provider": "neo4j",
                            "graph_query_summary": self._query_summary(
                                query=self.FILTERED_GRAPH_CONTEXT_QUERY,
                                row_count=len(graph_rows),
                                tokens=tokens,
                                search_mode="filtered_graph_context",
                            ),
                            "graph_rows_preview": self._rows_preview(graph_rows),
                            "graph_context": self._context_text(row),
                        }
                    }
                )
            )
        return candidates[: self.limit]

    def initialize(self) -> None:
        with self.driver.session() as session:
            session.execute_write(self._create_constraints)

    def clear(self) -> None:
        with self.driver.session() as session:
            session.execute_write(self._clear_graph)

    def upsert_record(self, record: KnowledgeRecord) -> None:
        with self.driver.session() as session:
            session.execute_write(self._upsert_record, record)

    @staticmethod
    def _create_constraints(tx: Any) -> None:
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Flow) REQUIRE f.flow_id IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Action) REQUIRE a.action IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Synonym) REQUIRE s.term IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:UserTask) REQUIRE t.task IS UNIQUE")
        tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (u:Utterance) REQUIRE u.text IS UNIQUE")

    @staticmethod
    def _clear_graph(tx: Any) -> None:
        tx.run(
            "MATCH (n) WHERE n:Flow OR n:Action OR n:Concept OR n:Synonym "
            "OR n:UserTask OR n:Utterance OR n:Ontology DETACH DELETE n"
        )

    @staticmethod
    def _upsert_record(tx: Any, record: KnowledgeRecord) -> None:
        tx.run(
            "MERGE (f:Flow {flow_id: $flow_id}) "
            "SET f.flow_name = $flow_name, f.source = $source, f.intent = $intent, "
            "f.business_event = $business_event, f.explanation = $explanation, f.confidence = $confidence",
            {
                "flow_id": record.flow_id,
                "flow_name": record.flow_name,
                "source": record.source,
                "intent": record.intent,
                "business_event": record.business_event,
                "explanation": record.explanation,
                "confidence": record.confidence,
            },
        )
        for action in record.capabilities:
            tx.run("MERGE (a:Action {action: $action}) SET a.type = coalesce(a.type, 'declared_action')", {"action": action})
            tx.run("MATCH (f:Flow {flow_id: $flow_id}), (a:Action {action: $action}) MERGE (f)-[:DECLARES_ACTION]->(a)", {"flow_id": record.flow_id, "action": action})
        for concept in record.concepts:
            tx.run("MERGE (c:Concept {name: $concept})", {"concept": concept})
            tx.run("MATCH (f:Flow {flow_id: $flow_id}), (c:Concept {name: $concept}) MERGE (f)-[:RELATES_TO]->(c)", {"flow_id": record.flow_id, "concept": concept})
            for alias in record.concept_aliases.get(concept, []):
                tx.run("MERGE (s:Synonym {term: $alias}) SET s.normalized = true", {"alias": alias})
                tx.run(
                    "MATCH (c:Concept {name: $concept}), (s:Synonym {term: $alias}) "
                    "MERGE (c)-[:HAS_SYNONYM]->(s) MERGE (s)-[:NORMALIZES_TO]->(c)",
                    {"concept": concept, "alias": alias},
                )
        for index, task in enumerate(record.user_tasks, start=1):
            sequence = task.sequence or index
            tx.run("MERGE (t:UserTask {task: $task}) SET t.type = $type", {"task": task.task, "type": task.type})
            tx.run(
                "MATCH (f:Flow {flow_id: $flow_id}), (t:UserTask {task: $task}) "
                "MERGE (f)-[rel:HAS_USER_TASK]->(t) SET rel.sequence = $sequence",
                {"flow_id": record.flow_id, "task": task.task, "sequence": sequence},
            )
            for action in task.front_actions:
                Neo4jKnowledgeGraphRepository._upsert_task_action(tx, record.flow_id, task.task, action.to_dict(), "HAS_FRONT_ACTION")
            for action in task.back_actions:
                Neo4jKnowledgeGraphRepository._upsert_task_action(tx, record.flow_id, task.task, action.to_dict(), "HAS_BACK_ACTION")
        for utterance in record.utterances[:20]:
            tx.run("MERGE (u:Utterance {text: $text})", {"text": utterance})
            tx.run("MATCH (f:Flow {flow_id: $flow_id}), (u:Utterance {text: $text}) MERGE (f)-[:EXEMPLIFIES]->(u)", {"flow_id": record.flow_id, "text": utterance})

    @staticmethod
    def _upsert_task_action(tx: Any, flow_id: str, task: str, action: dict[str, Any], relationship: str) -> None:
        tx.run(
            "MERGE (a:Action {action: $action}) "
            "SET a.type = $type, a.operation = $operation, a.resource = $resource, "
            "a.label = $label, a.triggers = $triggers, a.description = $description",
            action,
        )
        tx.run(
            f"MATCH (t:UserTask {{task: $task}}), (a:Action {{action: $action}}) MERGE (t)-[:{relationship}]->(a)",
            {"task": task, "action": action["action"]},
        )
        tx.run("MATCH (f:Flow {flow_id: $flow_id}), (a:Action {action: $action}) MERGE (f)-[:USES_ACTION]->(a)", {"flow_id": flow_id, "action": action["action"]})

    def _query_graph_context(self, tokens: list[str]) -> list[dict[str, Any]]:
        if not tokens:
            return self._query_all_graph_context()
        with self.driver.session() as session:
            return [
                dict(record)
                for record in session.run(
                    self.FILTERED_GRAPH_CONTEXT_QUERY,
                    {"tokens": tokens, "limit": self.limit},
                )
            ]

    def _query_all_graph_context(self) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return [dict(record) for record in session.run(self.GRAPH_CONTEXT_QUERY)]

    def _query_summary(
        self,
        query: str,
        row_count: int,
        tokens: list[str],
        search_mode: str,
    ) -> dict[str, Any]:
        compact_query = " ".join(query.split())
        return {
            "query": compact_query,
            "rows_returned": row_count,
            "limit": self.limit,
            "tokens": tokens,
            "search_mode": search_mode,
        }

    def _rows_preview(self, rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
        preview = []
        for row in rows[:limit]:
            preview.append(
                {
                    "flow_id": row.get("flow_id"),
                    "intent": row.get("intent"),
                    "business_event": row.get("business_event"),
                    "utterances": (row.get("utterances") or [])[:5],
                    "concepts": (row.get("concepts") or [])[:8],
                    "concept_aliases": (row.get("concept_aliases") or [])[:8],
                    "user_tasks": (row.get("user_tasks") or [])[:8],
                    "front_actions": (row.get("front_actions") or [])[:8],
                    "back_actions": (row.get("back_actions") or [])[:8],
                    "matched_tokens": row.get("matched_tokens") or [],
                    "match_score": row.get("match_score"),
                }
            )
        return preview


    def _context_text(self, row: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"flow_id: {row.get('flow_id')}",
                f"flow_name: {row.get('flow_name')}",
                f"intent: {row.get('intent')}",
                f"business_event: {row.get('business_event')}",
                f"utterances: {', '.join(row.get('utterances') or [])}",
                f"concepts: {', '.join(row.get('concepts') or [])}",
                f"concept_aliases: {', '.join(row.get('concept_aliases') or [])}",
                f"user_tasks: {', '.join(row.get('user_tasks') or [])}",
                f"front_actions: {', '.join(row.get('front_actions') or [])}",
                f"back_actions: {', '.join(row.get('back_actions') or [])}",
                f"explanation: {row.get('explanation') or ''}",
            ]
        )
