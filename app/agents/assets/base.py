from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.models import AgentDefinition, AgentPolicy, AgentRunResult
from app.agents.runtime import Agent


@dataclass(frozen=True)
class AssetSpecialistAgent(Agent):
    """Worker agent metadata and light analysis for one enterprise asset type."""

    agent_id: str = ""
    name: str = ""
    role: str = ""
    asset_type: str = ""
    skills: list[str] = field(default_factory=list)

    @property
    def definition(self) -> AgentDefinition:
        """Return the worker-agent metadata exposed to the registry."""
        return AgentDefinition(
            agent_id=self.agent_id,
            name=self.name,
            role=self.role,
            agent_class="worker",
            kind="worker",
            domain="asset",
            goals=[f"Handle {self.asset_type} assets consistently and audibly."],
            skills=self.skills,
            tool_ids=[],
            state_schema="AskAgentState|IngestionAgentState",
            policy=AgentPolicy(),
        )

    def run(self, input_data: Any, **kwargs: Any) -> AgentRunResult:
        """Return a traceable placeholder decision for this asset specialist."""
        return self._ok(
            {
                "asset_type": self.asset_type,
                "input": input_data,
                "decision": "specialist_registered",
            },
            trace=[
                {
                    "agent": self.definition.agent_id,
                    "asset_type": self.asset_type,
                    "skills": self.definition.skills,
                }
            ],
        )
