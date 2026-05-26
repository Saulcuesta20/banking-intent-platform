from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from importlib import import_module
from typing import Protocol


@dataclass(frozen=True)
class IngestionReasoningFinding:
    agent: str
    finding: str


@dataclass(frozen=True)
class IngestionReasoningResult:
    findings: list[IngestionReasoningFinding] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        if not self.findings:
            return ""
        lines = ["Ingestion reasoning findings:"]
        for finding in self.findings:
            lines.append(f"- {finding.agent}: {finding.finding}")
        return "\n".join(lines)


class IngestionReasoningProvider(Protocol):
    def analyze(self, corpus_summary: str) -> IngestionReasoningResult:
        """Analyze raw corpus context before flow/user-task extraction."""


class IngestionReasoningService:
    def __init__(self, provider: IngestionReasoningProvider):
        self.provider = provider

    def analyze(self, corpus_summary: str) -> IngestionReasoningResult:
        return self.provider.analyze(corpus_summary)


class NoopIngestionReasoningProvider:
    def analyze(self, corpus_summary: str) -> IngestionReasoningResult:
        return IngestionReasoningResult()


@dataclass(frozen=True)
class IngestionAgentSpec:
    name: str
    responsibility: str
    system_message: str


INGESTION_AGENT_SPECS = [
    IngestionAgentSpec(
        name="CorpusReaderAgent",
        responsibility="Read raw corpus and extract grounded business facts.",
        system_message=(
            "You are CorpusReaderAgent. Read the banking corpus carefully and identify only grounded facts: "
            "customer intents, business events, rules, entities, process steps, documents, channels, and evidence. "
            "Do not invent flows. Respond with concise FINDING lines."
        ),
    ),
    IngestionAgentSpec(
        name="FlowDesignerAgent",
        responsibility="Design complete business flows from grounded corpus evidence.",
        system_message=(
            "You are FlowDesignerAgent. Propose candidate banking flows only when the corpus supports an end-to-end "
            "business process. Name flow_id, intent, business_event, utterances, and high-level plan steps. "
            "Do not create unsupported processes. Respond with concise FINDING lines."
        ),
    ),
    IngestionAgentSpec(
        name="TaskDecomposerAgent",
        responsibility="Convert flow steps into reusable user tasks.",
        system_message=(
            "You are TaskDecomposerAgent. Convert candidate flow steps into reusable user_tasks. "
            "User tasks are human/business steps, not CRUD, API calls, calculations, validations, notifications, "
            "or persistence operations. Respond with concise FINDING lines."
        ),
    ),
    IngestionAgentSpec(
        name="ActionExtractorAgent",
        responsibility="Separate front actions from backend actions.",
        system_message=(
            "You are ActionExtractorAgent. Extract UI or channel events as front_actions and service/system/API "
            "operations as back_actions. Use resource.operation style names. Do not execute actions. "
            "Respond with concise FINDING lines."
        ),
    ),
    IngestionAgentSpec(
        name="ConceptAgent",
        responsibility="Identify concepts and retrieval anchors.",
        system_message=(
            "You are ConceptAgent. Identify domain concepts, entities, products, events, and synonyms that should "
            "be attached as concepts or utterances for future retrieval and explanation. "
            "Respond with concise FINDING lines."
        ),
    ),
    IngestionAgentSpec(
        name="ValidatorAgent",
        responsibility="Challenge and validate the candidate extraction.",
        system_message=(
            "You are ValidatorAgent. Review the other agents' findings. Reject unsupported inferred actions, "
            "missing user_task_refs, backend operations modeled as user_tasks, unclear concepts, and unsafe "
            "runtime assumptions. End with final validation guidance. Respond with concise FINDING lines."
        ),
    ),
]


class AutoGenIngestionReasoningProvider:
    """Run ingestion analysis with AutoGen AgentChat.

    AutoGen is used only during ingestion. Its output becomes context for the
    controlled JSON extractor and still goes through schema validation before
    anything is written to flow/user-task files or Neo4j.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_turns: int | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model or os.getenv("INGESTION_REASONING_MODEL") or os.getenv("FLOW_EXTRACTOR_MODEL") or "gpt-4o-mini"
        self.max_turns = max_turns or len(INGESTION_AGENT_SPECS)
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for AutoGen ingestion reasoning.")

    def analyze(self, corpus_summary: str) -> IngestionReasoningResult:
        return asyncio.run(self._analyze_async(corpus_summary))

    async def _analyze_async(self, corpus_summary: str) -> IngestionReasoningResult:
        agents_module = self._optional_import("autogen_agentchat.agents", "autogen-agentchat")
        teams_module = self._optional_import("autogen_agentchat.teams", "autogen-agentchat")
        conditions_module = self._optional_import("autogen_agentchat.conditions", "autogen-agentchat")
        openai_module = self._optional_import("autogen_ext.models.openai", "autogen-ext[openai]")

        AssistantAgent = agents_module.AssistantAgent
        RoundRobinGroupChat = teams_module.RoundRobinGroupChat
        MaxMessageTermination = conditions_module.MaxMessageTermination
        OpenAIChatCompletionClient = openai_module.OpenAIChatCompletionClient

        model_client_kwargs = {
            "model": self.model,
            "api_key": self.api_key,
        }
        if self.base_url:
            model_client_kwargs["base_url"] = self.base_url

        model_client = OpenAIChatCompletionClient(**model_client_kwargs)
        try:
            agents = [
                AssistantAgent(
                    spec.name,
                    model_client=model_client,
                    description=spec.responsibility,
                    system_message=spec.system_message,
                )
                for spec in INGESTION_AGENT_SPECS
            ]
            team = RoundRobinGroupChat(
                agents,
                termination_condition=MaxMessageTermination(self.max_turns),
            )
            result = await team.run(task=self._task_prompt(corpus_summary))
            return self._result_from_messages(result.messages)
        finally:
            close = getattr(model_client, "close", None)
            if close is not None:
                await close()

    def _task_prompt(self, corpus_summary: str) -> str:
        return (
            "Analyze this raw banking corpus before JSON extraction. "
            "Each agent must contribute only grounded findings for flow generation. "
            "Use short lines prefixed with FINDING:. The later extractor will produce the final schema.\n\n"
            "Required output focus:\n"
            "- candidate flows and intents\n"
            "- reusable user_tasks\n"
            "- front_actions and back_actions\n"
            "- business_events\n"
            "- concepts and utterances\n"
            "- validation risks\n\n"
            f"Corpus summary:\n{corpus_summary[:24000]}"
        )

    def _result_from_messages(self, messages: list[object]) -> IngestionReasoningResult:
        known_agents = {spec.name for spec in INGESTION_AGENT_SPECS}
        findings: list[IngestionReasoningFinding] = []
        for message in messages:
            source = str(getattr(message, "source", "") or "")
            if source not in known_agents:
                continue
            content = str(getattr(message, "content", "") or "").strip()
            if not content:
                continue
            for line in content.splitlines():
                text = line.strip().lstrip("-").strip()
                if text.upper().startswith("FINDING:"):
                    text = text.split(":", 1)[1].strip()
                if text:
                    findings.append(IngestionReasoningFinding(agent=source, finding=text))
        return IngestionReasoningResult(findings=findings)

    def _optional_import(self, module_name: str, friendly_name: str):
        try:
            return import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"Optional dependency '{friendly_name}' is required for AutoGen ingestion reasoning."
            ) from exc


class RoleBasedIngestionReasoningProvider:
    """Deterministic ingestion guidance for local runs and tests.

    The runtime ask path must stay constrained to validated flows. This provider
    mirrors the AutoGen agent responsibilities without making network calls.
    """

    def analyze(self, corpus_summary: str) -> IngestionReasoningResult:
        return IngestionReasoningResult(
            findings=[
                IngestionReasoningFinding(
                    agent="CorpusReaderAgent",
                    finding="Identify business events, customer intents, rules, entities, and reusable process steps from the raw corpus.",
                ),
                IngestionReasoningFinding(
                    agent="FlowDesignerAgent",
                    finding="Create complete business flows only when the corpus supports the process end to end.",
                ),
                IngestionReasoningFinding(
                    agent="TaskDecomposerAgent",
                    finding="Represent human or business steps as user_tasks and keep CRUD/API/calculation operations out of user_tasks.",
                ),
                IngestionReasoningFinding(
                    agent="ActionExtractorAgent",
                    finding="Separate UI-triggered front_actions from service or system back_actions.",
                ),
                IngestionReasoningFinding(
                    agent="ConceptAgent",
                    finding="Attach domain concepts that explain why a flow matches future customer questions.",
                ),
                IngestionReasoningFinding(
                    agent="ValidatorAgent",
                    finding="Reject missing references, backend operations modeled as user tasks, and unsupported inferred actions.",
                ),
            ]
        )
