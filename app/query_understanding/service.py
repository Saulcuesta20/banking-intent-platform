from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.ontology.service import OntologyTermNormalizer


@dataclass(frozen=True)
class QueryUnderstanding:
    original_question: str
    search_terms: list[str]
    entities: list[str] = field(default_factory=list)
    possible_intents: list[str] = field(default_factory=list)
    provider: str = "local"
    explanation: str = ""


class QueryUnderstandingProvider(Protocol):
    def understand(self, question: str) -> QueryUnderstanding:
        """Return graph search terms and domain hints for a natural-language question."""


class QueryUnderstandingService:
    def __init__(self, provider: QueryUnderstandingProvider):
        self.provider = provider

    def understand(self, question: str) -> QueryUnderstanding:
        return self.provider.understand(question)


class LocalQueryUnderstandingProvider:
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
        "favor",
        "por",
        "mi",
        "mis",
    }

    ENTITY_HINTS = {
        "prestamo": "Loan",
        "credito": "Loan",
        "refinanciar": "LoanRefinance",
        "cuota": "LoanConditions",
        "transferir": "Transfer",
        "transferencia": "Transfer",
        "cbu": "CBU",
        "cuenta": "SavingsAccount",
        "ahorro": "SavingsAccount",
        "pago": "Payment",
        "pagar": "Payment",
    }

    def __init__(self, ontology_normalizer: OntologyTermNormalizer | None = None):
        self.ontology_normalizer = ontology_normalizer or OntologyTermNormalizer()

    def understand(self, question: str) -> QueryUnderstanding:
        tokens = self._tokens(question)
        entities = []
        for token in tokens:
            entity = self.ENTITY_HINTS.get(token)
            if entity and entity not in entities:
                entities.append(entity)
        terms = self.ontology_normalizer.expand_search_terms(tokens)
        return QueryUnderstanding(
            original_question=question,
            search_terms=terms[:20],
            entities=entities,
            provider="local_query_understanding",
            explanation="Normalized terms plus ontology synonym aliases.",
        )

    def _tokens(self, question: str) -> list[str]:
        normalized = self._normalize_text(question)
        tokens = []
        seen = set()
        for token in re.findall(r"[a-z0-9_]+", normalized):
            if token in self.STOPWORDS or len(token) <= 3 or token in seen:
                continue
            tokens.append(token)
            seen.add(token)
        return tokens

    def _append_unique(self, values: list[str], seen: set[str], value: str) -> None:
        if value not in seen:
            values.append(value)
            seen.add(value)

    def _normalize_text(self, value: str) -> str:
        without_accents = unicodedata.normalize("NFKD", value)
        ascii_value = without_accents.encode("ascii", "ignore").decode("ascii")
        return ascii_value.lower()


class LLMQueryUnderstandingProvider:
    def __init__(
        self,
        fallback_provider: QueryUnderstandingProvider | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
    ):
        self.fallback_provider = fallback_provider or LocalQueryUnderstandingProvider()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("QUERY_UNDERSTANDING_MODEL") or os.getenv("INTENT_LLM_MODEL") or "gpt-4o-mini"
        self.timeout_seconds = timeout_seconds

    def understand(self, question: str) -> QueryUnderstanding:
        if not self.api_key:
            return self.fallback_provider.understand(question)
        try:
            answer = self._complete_json(question)
        except Exception:
            return self.fallback_provider.understand(question)

        fallback = self.fallback_provider.understand(question)
        terms = self._merge_unique(
            [str(value).lower() for value in answer.get("search_terms", [])],
            fallback.search_terms,
        )
        entities = self._merge_unique(
            [str(value) for value in answer.get("entities", [])],
            fallback.entities,
        )
        possible_intents = [str(value) for value in answer.get("possible_intents", [])][:8]
        return QueryUnderstanding(
            original_question=question,
            search_terms=terms[:24],
            entities=entities[:12],
            possible_intents=possible_intents,
            provider="llm_query_understanding",
            explanation=str(answer.get("explanation") or "LLM query expansion plus local fallback terms."),
        )

    def _complete_json(self, question: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You expand Spanish banking customer questions for graph retrieval. "
                        "Return only JSON. Do not select the final flow. Do not invent actions. "
                        "Focus on search terms, entities, synonyms, and possible intent hints."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Question:\n"
                        f"{question}\n\n"
                        "Return this JSON shape:\n"
                        "{\n"
                        '  "search_terms": ["short lowercase terms and synonyms"],\n'
                        '  "entities": ["DomainConcept"],\n'
                        '  "possible_intents": ["optional.flow.hints"],\n'
                        '  "explanation": "short reason"\n'
                        "}"
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Query understanding request failed: {exc.code} {detail}") from exc
        data = json.loads(raw)
        return json.loads(data["choices"][0]["message"]["content"])

    def _merge_unique(self, first: list[str], second: list[str]) -> list[str]:
        values = []
        seen = set()
        for value in [*first, *second]:
            normalized = value.strip()
            if not normalized or normalized.lower() in seen:
                continue
            values.append(normalized)
            seen.add(normalized.lower())
        return values
