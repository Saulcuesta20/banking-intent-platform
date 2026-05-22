from __future__ import annotations

import unicodedata
from pathlib import Path

from app.ingestion.flow_loader import FlowKnowledgeLoader
from app.models import KnowledgeRecord
from app.retrieval.providers import KnowledgeRetrievalProvider

STOPWORDS = {
    "como",
    "para",
    "pero",
    "quiero",
    "puedo",
    "hacer",
    "tengo",
    "necesito",
    "sobre",
    "desde",
    "donde",
    "cuando",
    "cual",
    "cuales",
    "este",
    "esta",
    "esto",
    "unos",
    "unas",
}


def normalize_text(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value)
    ascii_value = without_accents.encode("ascii", "ignore").decode("ascii")
    return ascii_value.lower()


class LocalKnowledgeRetrievalProvider(KnowledgeRetrievalProvider):
    def __init__(self, flow_directory: Path):
        self.flow_directory = flow_directory
        self.loader = FlowKnowledgeLoader()

    def retrieve(self, question: str) -> list[KnowledgeRecord]:
        records = self.loader.load_directory(self.flow_directory)
        normalized_question = normalize_text(question)
        scored = sorted(
            records,
            key=lambda record: self._score(normalized_question, record),
            reverse=True,
        )
        return [record for record in scored if self._score(normalized_question, record) >= 2]

    def _score(self, normalized_question: str, record: KnowledgeRecord) -> int:
        score = 0
        haystacks = record.utterances + [record.intent, record.business_event]
        for text in haystacks:
            normalized = normalize_text(text)
            if normalized and normalized in normalized_question:
                score += 3
        for node in record.ontology_nodes:
            aliases = record.ontology_aliases.get(node, [])
            normalized_aliases = [normalize_text(alias).replace("_", " ") for alias in aliases]
            if normalize_text(node).replace("_", " ") in normalized_question or any(
                alias and alias in normalized_question for alias in normalized_aliases
            ):
                score += 1
        for token in normalized_question.split():
            if token in STOPWORDS:
                continue
            if len(token) > 3 and token in normalize_text(" ".join(haystacks)):
                score += 1
        return score
