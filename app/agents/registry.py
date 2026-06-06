from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.runtime import Agent


@dataclass
class AgentRegistry:
    """In-memory registry for coordinator, delegator, and worker agents."""

    agents_by_id: dict[str, Agent] = field(default_factory=dict)

    @classmethod
    def from_agents(cls, agents: list[Agent]) -> "AgentRegistry":
        """Create a registry and register the provided agents by id."""
        registry = cls()
        for agent in agents:
            registry.register(agent)
        return registry

    def register(self, agent: Agent) -> None:
        """Add or replace one agent using its stable `agent_id`."""
        self.agents_by_id[agent.definition.agent_id] = agent

    def get(self, agent_id: str) -> Agent:
        """Return one registered agent or raise a clear missing-agent error."""
        try:
            return self.agents_by_id[agent_id]
        except KeyError as exc:
            raise KeyError(f"Agent not registered: {agent_id}") from exc

    def list_agents(self) -> list[Agent]:
        """Return registered agents sorted by id for stable output."""
        return [self.agents_by_id[key] for key in sorted(self.agents_by_id)]
