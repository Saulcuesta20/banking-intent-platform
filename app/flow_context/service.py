from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.models import KnowledgeRecord, Task


@dataclass(frozen=True)
class FlowAnswerContext:
    business_event: str
    plan: list[str]
    tasks: list[Task]
    related_capabilities: list[str]
    related_ontology_nodes: list[str]


class FlowAnswerContextService:
    """Project already-ingested flow knowledge for an ask response.

    This service does not create plans, tasks, events, actions, or ontology.
    Ingestion creates those artifacts. Runtime only selects a flow and projects
    the relevant fields into the answer.
    """

    def build(self, question: str, record: KnowledgeRecord) -> FlowAnswerContext:
        return FlowAnswerContext(
            business_event=record.business_event,
            plan=list(record.plan),
            tasks=list(record.tasks),
            related_capabilities=self._related_capabilities(record),
            related_ontology_nodes=self._related_ontology_nodes(question, record),
        )

    def _related_capabilities(self, record: KnowledgeRecord) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for value in record.capabilities:
            self._append_unique(values, seen, value)
        for user_task in record.user_tasks:
            for action in user_task.front_actions:
                self._append_unique(values, seen, action.action)
            for action in user_task.back_actions:
                self._append_unique(values, seen, action.action)
        return values

    def _related_ontology_nodes(self, question: str, record: KnowledgeRecord) -> list[str]:
        normalized_question = self._normalize_text(question)
        related = []
        remaining = []
        for node in record.ontology_nodes:
            normalized_node = self._normalize_text(node).replace("_", " ")
            normalized_aliases = [
                self._normalize_text(alias).replace("_", " ")
                for alias in record.ontology_aliases.get(node, [])
            ]
            if normalized_node and (
                normalized_node in normalized_question
                or any(alias and alias in normalized_question for alias in normalized_aliases)
            ):
                related.append(node)
            else:
                remaining.append(node)
        return related + remaining

    def _append_unique(self, values: list[str], seen: set[str], value: str) -> None:
        if value not in seen:
            values.append(value)
            seen.add(value)

    def _normalize_text(self, value: str) -> str:
        without_accents = unicodedata.normalize("NFKD", value)
        ascii_value = without_accents.encode("ascii", "ignore").decode("ascii")
        return ascii_value.lower()
