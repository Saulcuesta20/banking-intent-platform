from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.models import KnowledgeRecord, Task


@dataclass(frozen=True)
class AnswerContext:
    business_event: str
    plan: list[str]
    tasks: list[Task]
    related_capabilities: list[str]
    related_concepts: list[str]


class AnswerBuilder:
    """Project already-ingested knowledge for an ask response.

    This service does not create plans, tasks, events, tools, or concepts.
    Ingestion creates those artifacts. Runtime only selects a flow and projects
    the relevant fields into the answer.
    """

    def build(self, question: str, record: KnowledgeRecord) -> AnswerContext:
        return AnswerContext(
            business_event=record.business_event,
            plan=list(record.plan),
            tasks=list(record.tasks),
            related_capabilities=self._related_capabilities(record),
            related_concepts=self._related_concepts(question, record),
        )

    def _related_capabilities(self, record: KnowledgeRecord) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for value in record.capabilities:
            self._append_unique(values, seen, value)
        for user_task in record.user_tasks:
            for tool in user_task.tools:
                self._append_unique(values, seen, tool.tool_id)
        return values

    def _related_concepts(self, question: str, record: KnowledgeRecord) -> list[str]:
        normalized_question = self._normalize_text(question)
        related = []
        remaining = []
        for node in record.concepts:
            normalized_node = self._normalize_text(node).replace("_", " ")
            normalized_aliases = [
                self._normalize_text(alias).replace("_", " ")
                for alias in record.concept_aliases.get(node, [])
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
