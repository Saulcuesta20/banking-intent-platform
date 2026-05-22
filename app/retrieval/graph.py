from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ingestion.flow_loader import FlowKnowledgeLoader
from app.models import KnowledgeRecord
from app.query_understanding.service import LocalQueryUnderstandingProvider, QueryUnderstandingService
from app.retrieval.providers import KnowledgeRetrievalProvider


def _optional_import(module_name: str, friendly_name: str | None = None):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Optional dependency '{friendly_name or module_name}' is required for this provider."
        ) from exc


class GraphRAGKnowledgeRetrievalProvider(KnowledgeRetrievalProvider):
    """Retrieve candidate flows from Neo4j and attach graph context for LLM reasoning."""

    GRAPH_CONTEXT_QUERY = """
        MATCH (f:Flow)
        OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u:Utterance)
        OPTIONAL MATCH (f)-[:HAS_ONTOLOGY]->(o:Ontology)
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
          collect(DISTINCT o.name) AS ontology_nodes,
          collect(DISTINCT t.task) AS user_tasks,
          collect(DISTINCT front.action) AS front_actions,
          collect(DISTINCT back.action) AS back_actions
        ORDER BY flow_id
        """

    FILTERED_GRAPH_CONTEXT_QUERY = """
        MATCH (f:Flow)
        OPTIONAL MATCH (f)-[:EXEMPLIFIES]->(u_match:Utterance)
        OPTIONAL MATCH (f)-[:HAS_ONTOLOGY]->(o_match:Ontology)
        WITH f,
             collect(DISTINCT u_match.text) AS all_utterances,
             collect(DISTINCT o_match.name) AS all_ontology_nodes,
             toLower(
               coalesce(f.flow_id, '') + ' ' +
               coalesce(f.flow_name, '') + ' ' +
               coalesce(f.intent, '') + ' ' +
               coalesce(f.business_event, '') + ' ' +
               coalesce(f.explanation, '') + ' ' +
               reduce(text = '', value IN collect(DISTINCT u_match.text) | text + ' ' + coalesce(value, '')) + ' ' +
               reduce(text = '', value IN collect(DISTINCT o_match.name) | text + ' ' + coalesce(value, ''))
             ) AS haystack
        WITH f, all_utterances, all_ontology_nodes,
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
          all_ontology_nodes AS ontology_nodes,
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
        query_understanding_service: QueryUnderstandingService | None = None,
        limit: int = 50,
    ):
        neo4j = _optional_import("neo4j")
        self.driver = neo4j.GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.records = FlowKnowledgeLoader().load_directory(flow_directory)
        self.records_by_flow_id = {record.flow_id: record for record in self.records}
        self.query_understanding_service = query_understanding_service or QueryUnderstandingService(
            LocalQueryUnderstandingProvider()
        )
        self.limit = limit

    def retrieve(self, question: str) -> list[KnowledgeRecord]:
        understanding = self.query_understanding_service.understand(question)
        tokens = understanding.search_terms
        graph_rows = self._query_graph_context(tokens)
        if not graph_rows:
            fallback_rows = self._query_all_graph_context()
            return [
                record.model_copy(
                    update={
                        "metadata": {
                            **record.metadata,
                            "retrieval_provider": "graph_rag_neo4j_empty_fallback",
                            "graph_query_summary": self._query_summary(
                                query=self.GRAPH_CONTEXT_QUERY,
                                row_count=len(fallback_rows),
                                tokens=tokens,
                                fallback=True,
                            ),
                            "graph_rows_preview": [],
                            "query_understanding": understanding.__dict__,
                        }
                    }
                )
                for record in self.records[: self.limit]
            ]

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
                            "retrieval_provider": "graph_rag_neo4j",
                            "graph_query_summary": self._query_summary(
                                query=self.FILTERED_GRAPH_CONTEXT_QUERY,
                                row_count=len(graph_rows),
                                tokens=tokens,
                                fallback=False,
                            ),
                            "graph_rows_preview": self._rows_preview(graph_rows),
                            "graph_context": self._context_text(row),
                            "query_understanding": understanding.__dict__,
                        }
                    }
                )
            )
        return candidates[: self.limit]

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
        fallback: bool,
    ) -> dict[str, Any]:
        compact_query = " ".join(query.split())
        return {
            "query": compact_query,
            "rows_returned": row_count,
            "limit": self.limit,
            "tokens": tokens,
            "fallback": fallback,
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
                    "ontology_nodes": (row.get("ontology_nodes") or [])[:8],
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
                f"ontology_nodes: {', '.join(row.get('ontology_nodes') or [])}",
                f"user_tasks: {', '.join(row.get('user_tasks') or [])}",
                f"front_actions: {', '.join(row.get('front_actions') or [])}",
                f"back_actions: {', '.join(row.get('back_actions') or [])}",
                f"explanation: {row.get('explanation') or ''}",
            ]
        )
