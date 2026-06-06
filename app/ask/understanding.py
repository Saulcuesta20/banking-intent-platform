from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.tools.models import ToolDefinition


@dataclass(frozen=True)
class QuestionUnderstanding:
    original_question: str
    search_terms: list[str]
    corrected_question: str | None = None
    corrections: list[dict[str, str]] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    possible_intents: list[str] = field(default_factory=list)
    ask_posture: str = "unknown"
    inferred_needs: list[dict[str, Any]] = field(default_factory=list)
    routing_hints: dict[str, Any] = field(default_factory=dict)
    ambiguity: dict[str, Any] | None = None
    provider: str = "llm_required"
    explanation: str = ""


class QuestionUnderstandingProvider(Protocol):
    def understand(self, question: str) -> QuestionUnderstanding:
        """Return graph search terms and domain hints for a natural-language question."""


@dataclass(frozen=True)
class QuestionUnderstandingService:
    provider: QuestionUnderstandingProvider

    def understand(self, question: str) -> QuestionUnderstanding:
        return self.provider.understand(question)


class LLMQuestionUnderstandingProvider:
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
        self.tool_definition = ToolDefinition(
            tool_id="llm.question_understanding.complete_json",
            tool_type="llm_tool",
            operation="understand_question",
            resource="ask.question_understanding",
            label="Question understanding LLM",
            description="Corrects, classifies, and expands a user question for routing.",
            llm_operation="json_completion",
            llm_model=self.model,
            llm_provider="openai_compatible",
            endpoint=f"{self.base_url}/chat/completions",
        )
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM query understanding.")

    def understand(self, question: str) -> QuestionUnderstanding:
        answer = self._complete_json(question)
        terms = self._merge_unique([str(value).lower() for value in answer.get("search_terms", [])])
        entities = self._merge_unique([str(value) for value in answer.get("entities", [])])
        possible_intents = [str(value) for value in answer.get("possible_intents", [])][:8]
        inferred_needs = [
            value
            for value in answer.get("inferred_needs", [])
            if isinstance(value, dict)
        ][:8]
        routing_hints = answer.get("routing_hints") if isinstance(answer.get("routing_hints"), dict) else {}
        corrections = [
            {"from": str(value.get("from", "")), "to": str(value.get("to", ""))}
            for value in answer.get("corrections", [])
            if isinstance(value, dict) and value.get("from") and value.get("to")
        ]
        ambiguity = answer.get("ambiguity") if isinstance(answer.get("ambiguity"), dict) else None
        return QuestionUnderstanding(
            original_question=question,
            corrected_question=str(answer.get("corrected_question") or ""),
            corrections=corrections,
            search_terms=terms[:24],
            entities=entities[:12],
            possible_intents=possible_intents,
            ask_posture=str(answer.get("ask_posture") or "unknown"),
            inferred_needs=inferred_needs,
            routing_hints=routing_hints,
            ambiguity=ambiguity,
            provider="llm_question_understanding",
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
                        "You expand Spanish banking customer questions for knowledge graph search. "
                        "Return only JSON. Do not execute banking tools. "
                        "Correct obvious typos, detect ambiguity, infer the user's ask posture, "
                        "and suggest possible existing intent hints. "
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
                        '  "ask_posture": "doubt|consultation|problem|execution_request|tool_explanation|mixed|unsupported",\n'
                        '  "inferred_needs": [\n'
                        '    {"kind": "question|execution|explanation|clarification|unsupported", "text": "fragment", "confidence": 0.0, "reason": "why"}\n'
                        "  ],\n"
                        '  "routing_hints": {\n'
                        '    "needs_answer": true|false,\n'
                        '    "needs_flow": true|false,\n'
                        '    "needs_process": true|false,\n'
                        '    "needs_tool_explanation": true|false,\n'
                        '    "needs_clarification": true|false,\n'
                        '    "intention_relation": "single|complementary|competing|unknown"\n'
                        "  },\n"
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
