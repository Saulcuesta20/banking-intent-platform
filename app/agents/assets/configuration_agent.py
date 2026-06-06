from dataclasses import dataclass, field

from app.agents.assets.base import AssetSpecialistAgent


@dataclass(frozen=True)
class ConfigurationAgent(AssetSpecialistAgent):
    """Worker agent for routing, source, and runtime configuration assets."""

    agent_id: str = "agent.asset.configuration"
    name: str = "Configuration Agent"
    role: str = "Apply routing, source, and runtime configuration knowledge."
    asset_type: str = "configuration"
    skills: list[str] = field(default_factory=lambda: ["configuration_lookup", "routing_policy", "source_policy"])
