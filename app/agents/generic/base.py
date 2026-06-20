from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.engine import AgentEngine
from app.agents.models import AgentDefinition, AgentRunResult
from app.agents.runtime import Agent


@dataclass(frozen=True)
class ConfiguredAgent(Agent):
    """Generic agent backed by a declarative definition.

    This is the base for configurable business agents loaded from YAML. The
    runtime remains class-based, but the operational contract comes from the
    definition, not from ad hoc code.
    """

    spec: AgentDefinition
    engine: AgentEngine = field(default_factory=AgentEngine, repr=False, compare=False)

    @property
    def definition(self) -> AgentDefinition:
        return self.spec

    def run(self, input_data: Any, **kwargs: Any) -> AgentRunResult:
        return self.engine.run(self.definition, input_data)
