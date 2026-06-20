from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.models import AgentDefinition, AgentPolicy, AgentRunResult
from app.agents.runtime import Agent
from app.knowledge_base.source_router import KnowledgeSourceRouter


@dataclass(frozen=True)
class KnowledgeRouterAgent(Agent):
    """Delegator agent that chooses which knowledge sources/views to consult."""

    router: KnowledgeSourceRouter = field(default_factory=KnowledgeSourceRouter)

    @property
    def definition(self) -> AgentDefinition:
        """Return metadata for the delegator that selects knowledge sources."""
        return AgentDefinition(
            agent_id="agent.ask.knowledge_router",
            name="Knowledge Router Agent",
            role="Route an understood question to the right knowledge sources and storage views.",
            agent_class="delegator",
            kind="delegator",
            domain="ask",
            goals=[
                "Select one or more knowledge sources for an ask.",
                "Allow complementary retrieval across QA, flows/processes, rules, tools, configuration, and entities.",
            ],
            skills=["knowledge_source_routing", "multi_source_retrieval", "asset_view_selection"],
            tool_ids=[],
            graph_name="langgraph_ask",
            state_schema="AskAgentState",
            policy=AgentPolicy(),
        )

    def run(self, input_data: dict[str, Any], **kwargs: Any) -> AgentRunResult:
        """Route an understood question to one or more knowledge sources."""
        routes = self.router.route(
            question=str(input_data.get("question") or ""),
            search_terms=[str(value) for value in input_data.get("search_terms", [])],
            question_understanding=input_data.get("question_understanding"),
            asset_search=input_data.get("asset_search"),
        )
        payload = [route.model_dump(mode="json") for route in routes]
        return self._ok(
            output=payload,
            trace=[
                {
                    "agent": self.definition.agent_id,
                    "sources": [route["source"] for route in payload],
                    "views": sorted({view for route in payload for view in route["views"]}),
                }
            ],
        )
