from dataclasses import dataclass, field

from app.agents.assets.base import AssetSpecialistAgent


@dataclass(frozen=True)
class EntityAgent(AssetSpecialistAgent):
    """Worker agent for entity/concept vocabulary and synonym expansion."""

    agent_id: str = "agent.asset.entity"
    name: str = "Entity Agent"
    role: str = "Normalize business entities, concepts, synonyms, and relationship vocabulary."
    asset_type: str = "entity"
    skills: list[str] = field(default_factory=lambda: ["entity_normalization", "synonym_expansion", "relationship_linking"])
