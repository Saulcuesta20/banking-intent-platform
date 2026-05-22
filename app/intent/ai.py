from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from importlib import import_module
from typing import Any, Protocol

from app.intent.providers import SemanticReasoningProvider
from app.models import KnowledgeRecord


def _optional_import(module_name: str, friendly_name: str | None = None):
    try:
        return import_module(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Optional dependency '{friendly_name or module_name}' is required for this provider."
        ) from exc


class JSONLLMClient(Protocol):
    def complete_json(self, prompt: str) -> dict[str, Any]:
        pass


class OpenAIJSONClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("INTENT_LLM_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required when USE_AI_PROVIDERS=true.")

    def complete_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a constrained banking GraphRAG intent classifier. "
                        "Use only the graph context provided by the application. "
                        "Do not invent intents, user tasks, or actions."
                    ),
                },
                {"role": "user", "content": prompt},
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
            raise RuntimeError(f"LLM request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


class LLMDecisionRecorder:
    def __init__(self):
        self.prompt: str = ""
        self.answer: dict[str, Any] = {}

    def record(self, prompt: str, answer: dict[str, Any]) -> None:
        self.prompt = prompt
        self.answer = dict(answer)


class LangchainGraphRAGReasoningProvider(SemanticReasoningProvider):
    """Use LangChain prompt templating plus an LLM to choose only valid graph flows."""

    def __init__(
        self,
        openai_api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        llm_client: JSONLLMClient | None = None,
        decision_recorder: LLMDecisionRecorder | None = None,
    ):
        self.PromptTemplate = self._load_prompt_template()
        self.llm_client = llm_client or OpenAIJSONClient(
            api_key=openai_api_key,
            base_url=base_url,
            model=model,
        )
        self.decision_recorder = decision_recorder or LLMDecisionRecorder()

    def classify_intent(
        self, question: str, records: list[KnowledgeRecord]
    ) -> KnowledgeRecord | None:
        if not records:
            return None

        prompt = self.PromptTemplate(
            input_variables=["question", "query_understanding", "graph_context"],
            template=(
                "Customer question:\n"
                "{question}\n\n"
                "LLM query understanding context:\n"
                "{query_understanding}\n\n"
                "Valid banking graph context follows. These are the only allowed flows, "
                "user tasks, front actions, and back actions:\n"
                "{graph_context}\n\n"
                "Return only JSON with this exact shape:\n"
                "{{\n"
                '  "can_resolve": true|false,\n'
                '  "selected_flow_id": "flow_id or unknown",\n'
                '  "confidence": 0.0,\n'
                '  "reason": "short explanation grounded in graph context"\n'
                "}}\n\n"
                "Rules:\n"
                "- If no flow clearly matches the question, return can_resolve=false and selected_flow_id=unknown.\n"
                "- If a flow matches, selected_flow_id must be exactly one flow_id from the graph context.\n"
                "- If query understanding says the request is ambiguous and the user did not explicitly ask for one candidate flow, return can_resolve=false.\n"
                "- Do not choose a broad domain-support flow just because it is loosely related to the words in the question.\n"
                "- If the customer needs a clarification question before choosing between multiple possible intents, return can_resolve=false.\n"
                "- Do not propose tasks or actions that are not in the graph context.\n"
            ),
        ).format(
            question=question,
            query_understanding=self._query_understanding_context(records),
            graph_context=self._graph_context(records),
        )
        answer = self.llm_client.complete_json(prompt)
        self.decision_recorder.record(prompt, answer)
        if not bool(answer.get("can_resolve")):
            return None

        selected_flow_id = str(answer.get("selected_flow_id", "")).strip().lower()
        for record in records:
            if record.flow_id.lower() == selected_flow_id:
                confidence = float(answer.get("confidence", record.confidence) or record.confidence)
                reason = str(answer.get("reason") or record.explanation)
                return record.model_copy(
                    update={
                        "confidence": max(0.0, min(confidence, 1.0)),
                        "explanation": f"GraphRAG LLM decision: {reason}",
                        "metadata": {
                            **record.metadata,
                            "reasoning_provider": "langchain_graph_rag_llm",
                            "llm_reason": reason,
                            "llm_prompt": prompt,
                            "llm_prompt_summary": self._prompt_summary(prompt),
                            "llm_answer": answer,
                        },
                    }
                )
        return None

    def _prompt_summary(self, prompt: str) -> dict[str, Any]:
        return {
            "chars": len(prompt),
            "preview": prompt[:1200],
        }

    def _graph_context(self, records: list[KnowledgeRecord]) -> str:
        blocks = []
        for record in records:
            context = record.metadata.get("graph_context")
            if context:
                blocks.append(self._compact_graph_context(context))
            else:
                blocks.append(
                    "\n".join(
                        [
                            f"flow_id: {record.flow_id}",
                            f"flow_name: {record.flow_name}",
                            f"intent: {record.intent}",
                            f"business_event: {record.business_event}",
                            f"utterances: {', '.join(record.utterances)}",
                            f"ontology_nodes: {', '.join(record.ontology_nodes)}",
                            f"ontology_aliases: {self._alias_text(record.ontology_aliases)}",
                            f"explanation: {record.explanation}",
                        ]
                    )
                )
        return "\n\n---\n\n".join(blocks)

    def _query_understanding_context(self, records: list[KnowledgeRecord]) -> str:
        metadata = records[0].metadata if records else {}
        understanding = metadata.get("query_understanding") or {}
        if not isinstance(understanding, dict):
            return "{}"
        return json.dumps(
            {
                "corrected_question": understanding.get("corrected_question"),
                "corrections": understanding.get("corrections"),
                "search_terms": understanding.get("search_terms"),
                "entities": understanding.get("entities"),
                "possible_intents": understanding.get("possible_intents"),
                "ambiguity": understanding.get("ambiguity"),
                "explanation": understanding.get("explanation"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def _compact_graph_context(self, context: str) -> str:
        keep_prefixes = (
            "flow_id:",
            "flow_name:",
            "intent:",
            "business_event:",
            "utterances:",
            "ontology_nodes:",
            "ontology_aliases:",
            "explanation:",
        )
        lines = []
        for line in context.splitlines():
            if line.startswith(keep_prefixes):
                lines.append(self._trim_context_line(line))
        return "\n".join(lines)

    def _trim_context_line(self, line: str, max_items: int = 6) -> str:
        if ":" not in line or "," not in line:
            return line
        label, values = line.split(":", 1)
        items = [item.strip() for item in values.split(",") if item.strip()]
        if len(items) <= max_items:
            return line
        return f"{label}: {', '.join(items[:max_items])}, ..."

    def _alias_text(self, aliases: dict[str, list[str]]) -> str:
        values = []
        for node, node_aliases in aliases.items():
            values.append(f"{node} => {', '.join(node_aliases)}")
        return "; ".join(values)

    def _load_prompt_template(self):
        try:
            module = _optional_import("langchain_core.prompts", "langchain-core")
            return module.PromptTemplate
        except RuntimeError:
            module = _optional_import("langchain.prompts", "langchain")
            return module.PromptTemplate


# Backward-compatible name used by older factory imports/docs.
LangchainReasoningProvider = LangchainGraphRAGReasoningProvider
