from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.models import AgentDefinition, AgentPolicy, AgentRunResult
from app.agents.runtime import Agent
from app.ingestion.orchestrator import IngestionOrchestratorConfig, IngestionOrchestratorService


@dataclass(frozen=True)
class IngestionCoordinatorAgent(Agent):
    """Coordinator agent for corpus ingestion.

    The current implementation delegates execution to the ingestion
    orchestrator, which owns the LangGraph-backed ingestion graph.
    """

    orchestrator: IngestionOrchestratorService

    @property
    def definition(self) -> AgentDefinition:
        """Return metadata for the coordinator that owns ingestion runs."""
        return AgentDefinition(
            agent_id="agent.ingestion.coordinator",
            name="Ingestion Coordinator Agent",
            role="Coordinate corpus scanning, classification, extraction, validation, artifact writing, and audit.",
            kind="coordinator",
            domain="ingestion",
            goals=[
                "Turn raw enterprise corpus into governed knowledge assets.",
                "Keep extraction auditable and reviewable before knowledge-base sync.",
            ],
            skills=["corpus_scan", "semantic_classification", "asset_extraction", "asset_validation", "audit"],
            graph_name="ingestion_orchestrator",
            state_schema="IngestionAgentState",
            policy=AgentPolicy(requires_human_review=True),
        )

    def run(self, input_data: IngestionOrchestratorConfig, **kwargs: Any) -> AgentRunResult:
        """Run the ingestion orchestrator and expose its steps as agent trace."""
        try:
            result = self.orchestrator.run(input_data)
        except Exception as exc:
            return self._failed(exc)
        return self._ok(
            output=result,
            trace=[
                {
                    "agent": self.definition.agent_id,
                    "graph": self.definition.graph_name,
                    "steps": result.steps,
                }
            ],
        )
