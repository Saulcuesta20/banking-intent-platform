from __future__ import annotations

import os
from pathlib import Path

from app.ingestion.flow_loader import FlowKnowledgeLoader
from app.models import KnowledgeRecord
from app.retrieval.providers import KnowledgeRetrievalProvider


def _optional_import(module_name: str, friendly_name: str | None = None):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Optional dependency '{friendly_name or module_name}' is required for this provider."
        ) from exc


class LlamaIndexKnowledgeRetrievalProvider(KnowledgeRetrievalProvider):
    def __init__(
        self,
        flow_directory: Path,
        openai_api_key: str | None = None,
        qdrant_host: str | None = None,
        qdrant_api_key: str | None = None,
    ):
        self.flow_directory = flow_directory
        self.qdrant_host = qdrant_host
        self.qdrant_api_key = qdrant_api_key
        self.loader = FlowKnowledgeLoader()
        self.records = self.loader.load_directory(flow_directory)
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.documents = []
        self._prepare_documents()

    def _prepare_documents(self) -> None:
        llama_index = _optional_import("llama_index")
        Document = getattr(llama_index, "Document", None)
        if Document is None:
            raise RuntimeError("llama_index.Document is required for LlamaIndex retrieval.")

        self.documents = [
            Document(
                text=self._record_text(record),
                extra_info={"source": record.source, "intent": record.intent},
            )
            for record in self.records
        ]

    def _record_text(self, record: KnowledgeRecord) -> str:
        return (
            f"Intent: {record.intent}\n"
            f"Business event: {record.business_event}\n"
            f"Utterances: {'; '.join(record.utterances)}\n"
            f"Plan steps: {'; '.join(record.plan)}\n"
            f"Capabilities: {'; '.join(record.capabilities)}\n"
            f"Ontology nodes: {'; '.join(record.ontology_nodes)}\n"
            f"Ontology aliases: {self._alias_text(record.ontology_aliases)}\n"
            f"Explanation: {record.explanation}"
        )

    def retrieve(self, question: str) -> list[KnowledgeRecord]:
        if not self.records:
            return []

        scored = sorted(
            self.records,
            key=lambda record: self._score(question, record),
            reverse=True,
        )
        return [record for record in scored if self._score(question, record) > 0]

    def _score(self, question: str, record: KnowledgeRecord) -> int:
        score = 0
        normalized_question = question.lower()
        alias_values = [alias for aliases in record.ontology_aliases.values() for alias in aliases]
        for text in [record.intent, record.business_event] + record.utterances + record.ontology_nodes + alias_values:
            if text.lower() in normalized_question:
                score += 4
        for token in normalized_question.split():
            if len(token) > 3 and token in record.explanation.lower():
                score += 1
        return score

    def _alias_text(self, aliases: dict[str, list[str]]) -> str:
        return "; ".join(
            f"{node} => {', '.join(node_aliases)}"
            for node, node_aliases in aliases.items()
        )
