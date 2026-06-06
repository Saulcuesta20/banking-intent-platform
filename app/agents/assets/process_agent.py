from dataclasses import dataclass, field

from app.agents.assets.base import AssetSpecialistAgent


@dataclass(frozen=True)
class ProcessAgent(AssetSpecialistAgent):
    """Worker agent for executable process definitions and workflow readiness."""

    agent_id: str = "agent.asset.process"
    name: str = "Process Agent"
    role: str = "Evaluate executable process definitions, nodes, transitions, rules, and exceptions."
    asset_type: str = "process"
    skills: list[str] = field(default_factory=lambda: ["process_routing", "workflow_validation", "execution_readiness"])
