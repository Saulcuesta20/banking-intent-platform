from dataclasses import dataclass, field

from app.agents.assets.base import AssetSpecialistAgent


@dataclass(frozen=True)
class RuleAgent(AssetSpecialistAgent):
    """Worker agent for rules, policies, constraints, and decision gates."""

    agent_id: str = "agent.asset.rule"
    name: str = "Rule Agent"
    role: str = "Retrieve and validate policy, eligibility, and business-rule constraints."
    asset_type: str = "business_rule"
    skills: list[str] = field(default_factory=lambda: ["rule_retrieval", "constraint_checking", "decision_explanation"])
