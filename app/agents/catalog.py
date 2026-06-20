from __future__ import annotations

from app.agents.catalog_loader import AgentCatalogLoader
from app.agents.assets import (
    ConfigurationAgent,
    EntityAgent,
    FlowAgent,
    ProcessAgent,
    QAAgent,
    RuleAgent,
    ToolAgent,
)
from app.agents.ask import KnowledgeRouterAgent
from app.agents.generic import build_agents_from_definitions
from app.agents.registry import AgentRegistry
from app.agents.runtime import Agent
from app.config.settings import load_settings


def build_asset_specialist_agents() -> list[Agent]:
    """Create the default worker agents for each supported asset type."""
    return [
        FlowAgent(),
        ProcessAgent(),
        RuleAgent(),
        QAAgent(),
        EntityAgent(),
        ToolAgent(),
        ConfigurationAgent(),
    ]


def build_configured_agents() -> list[Agent]:
    """Load configurable business agents from the YAML catalog."""
    settings = load_settings()
    definitions = AgentCatalogLoader().load_file(settings.agent_catalog_path)
    return build_agents_from_definitions(definitions)


def build_agent_registry(extra_agents: list[Agent] | None = None) -> AgentRegistry:
    """Create the default agent registry and append optional custom agents."""
    return AgentRegistry.from_agents([
        *build_configured_agents(),
        KnowledgeRouterAgent(),
        *build_asset_specialist_agents(),
        *(extra_agents or []),
    ])
