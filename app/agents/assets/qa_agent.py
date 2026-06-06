from dataclasses import dataclass, field

from app.agents.assets.base import AssetSpecialistAgent


@dataclass(frozen=True)
class QAAgent(AssetSpecialistAgent):
    """Worker agent for approved question-and-answer knowledge assets."""

    agent_id: str = "agent.asset.qa"
    name: str = "QA Agent"
    role: str = "Answer approved Q&A knowledge items with grounded evidence."
    asset_type: str = "qa"
    skills: list[str] = field(default_factory=lambda: ["direct_answer", "evidence_selection", "citation_projection"])
