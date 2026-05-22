from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class QueryUnderstanding:
    original_question: str
    search_terms: list[str]
    corrected_question: str | None = None
    corrections: list[dict[str, str]] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    possible_intents: list[str] = field(default_factory=list)
    ambiguity: dict[str, Any] | None = None
    provider: str = "llm_required"
    explanation: str = ""


class QueryUnderstandingProvider(Protocol):
    def understand(self, question: str) -> QueryUnderstanding:
        """Return graph search terms and domain hints for a natural-language question."""


class QueryUnderstandingService:
    def __init__(self, provider: QueryUnderstandingProvider):
        self.provider = provider

    def understand(self, question: str) -> QueryUnderstanding:
        return self.provider.understand(question)


class LLMQueryUnderstandingProvider:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("QUERY_UNDERSTANDING_MODEL") or os.getenv("INTENT_LLM_MODEL") or "gpt-4o-mini"
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM query understanding.")

    def understand(self, question: str) -> QueryUnderstanding:
        answer = self._complete_json(question)
        terms = self._merge_unique([str(value).lower() for value in answer.get("search_terms", [])])
        entities = self._merge_unique([str(value) for value in answer.get("entities", [])])
        possible_intents = [str(value) for value in answer.get("possible_intents", [])][:8]
        corrections = [
            {"from": str(value.get("from", "")), "to": str(value.get("to", ""))}
            for value in answer.get("corrections", [])
            if isinstance(value, dict) and value.get("from") and value.get("to")
        ]
        ambiguity = answer.get("ambiguity") if isinstance(answer.get("ambiguity"), dict) else None
        return QueryUnderstanding(
            original_question=question,
            corrected_question=str(answer.get("corrected_question") or ""),
            corrections=corrections,
            search_terms=terms[:24],
            entities=entities[:12],
            possible_intents=possible_intents,
            ambiguity=ambiguity,
            provider="llm_query_understanding",
            explanation=str(answer.get("explanation") or "LLM query correction and expansion."),
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
                        "Return only JSON. Do not execute banking actions. "
                        "Correct obvious typos, detect ambiguity, and suggest possible existing intent hints. "
                        "Do not select the final flow."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Question:\n"
                        f"{question}\n\n"
                        "Return this JSON shape:\n"
                        "{\n"
                        '  "corrected_question": "question with obvious typos corrected, or original",\n'
                        '  "corrections": [{"from": "bad token", "to": "correct token"}],\n'
                        '  "search_terms": ["short lowercase terms and synonyms"],\n'
                        '  "entities": ["DomainConcept"],\n'
                        '  "possible_intents": ["optional.flow.hints"],\n'
                        '  "ambiguity": {"is_ambiguous": true|false, "reason": "why", "options": ["possible intents"]},\n'
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

    def _merge_unique(self, values_to_merge: list[str]) -> list[str]:
        values = []
        seen = set()
        for value in values_to_merge:
            normalized = value.strip()
            if not normalized or normalized.lower() in seen:
                continue
            values.append(normalized)
            seen.add(normalized.lower())
        return values
