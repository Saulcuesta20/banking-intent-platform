from __future__ import annotations

from typing import Iterable

from app.agents.generic.coordinator import GenericCoordinatorAgent
from app.agents.generic.delegator import GenericDelegatorAgent
from app.agents.generic.monitoring import GenericMonitoringAgent
from app.agents.generic.planning import GenericPlanningAgent
from app.agents.generic.worker import GenericWorkerAgent
from app.agents.models import AgentDefinition
from app.agents.runtime import Agent


_AGENT_CLASS_MAP = {
    "planning": GenericPlanningAgent,
    "coordinator": GenericCoordinatorAgent,
    "delegator": GenericDelegatorAgent,
    "worker": GenericWorkerAgent,
    "monitoring": GenericMonitoringAgent,
}


def build_agent_from_definition(definition: AgentDefinition) -> Agent:
    agent_class = _AGENT_CLASS_MAP.get(definition.agent_class, GenericWorkerAgent)
    return agent_class(definition)


def build_agents_from_definitions(definitions: Iterable[AgentDefinition]) -> list[Agent]:
    return [build_agent_from_definition(definition) for definition in definitions if definition.enabled]
