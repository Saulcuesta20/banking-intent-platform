from dataclasses import dataclass, field

from app.agents.assets.base import AssetSpecialistAgent


@dataclass(frozen=True)
class FlowAgent(AssetSpecialistAgent):
    """Worker agent for selecting and explaining user-facing flow assets."""

    agent_id: str = "agent.asset.flow"
    name: str = "Flow Agent"
    role: str = "Evaluate user-facing flow candidates and flow route evidence."
    asset_type: str = "flow"
    skills: list[str] = field(default_factory=lambda: ["flow_selection", "intent_mapping", "execution_option_preview"])
