from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.models import AgentDefinition, AgentPolicy, AgentRunResult
from app.agents.runtime import Agent
from app.ask.service import AskService


@dataclass(frozen=True)
class AskCoordinatorAgent(Agent):
    """Coordinator agent for end-to-end question resolution."""

    ask_service: AskService

    @property
    def definition(self) -> AgentDefinition:
        """Return metadata for the coordinator that owns the ask workflow."""
        return AgentDefinition(
            agent_id="agent.ask.coordinator",
            name="Ask Coordinator Agent",
            role="Coordinate question understanding, retrieval, routing, planning, answer building, approval, and audit.",
            kind="coordinator",
            domain="ask",
            goals=[
                "Resolve user questions with grounded knowledge-base evidence.",
                "Route Q&A, flow, process, explanation, execution, clarification, and multiple-intention asks.",
            ],
            skills=["question_understanding", "rag_retrieval", "goal_routing", "planning", "answer_projection"],
            graph_name="langgraph_ask",
            state_schema="AskAgentState",
            policy=AgentPolicy(requires_human_review=False),
        )

    def run(self, input_data: str, **kwargs: Any) -> AgentRunResult:
        """Resolve one user question through `AskService` and capture trace events."""
        trace_events: list[dict[str, Any]] = []

        def trace(step: str, detail: str) -> None:
            trace_events.append({"step": step, "detail": detail})

        try:
            result = self.ask_service.resolve(input_data, trace=trace)
        except Exception as exc:
            return self._failed(exc, trace_events)
        return self._ok(output=result, trace=trace_events)
