from dataclasses import dataclass, field

from app.agents.assets.base import AssetSpecialistAgent


@dataclass(frozen=True)
class ToolAgent(AssetSpecialistAgent):
    """Worker agent for frontend, backend, and LLM tool knowledge."""

    agent_id: str = "agent.asset.tool"
    name: str = "Tool Agent"
    role: str = "Explain tool capabilities and validate frontend, backend, and LLM tool availability."
    asset_type: str = "tool"
    skills: list[str] = field(default_factory=lambda: ["tool_lookup", "tool_explanation", "tool_policy_check"])
