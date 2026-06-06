from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.agents.models import AgentDefinition, AgentRunResult


class Agent(ABC):
    """Base class for platform agents.

    LangGraph remains the execution engine for graph-shaped workflows. This
    class gives the platform a stable agent identity, role, policy, and trace
    envelope around those workflows.
    """

    @property
    @abstractmethod
    def definition(self) -> AgentDefinition:
        """Return the stable runtime identity for this agent."""

    @abstractmethod
    def run(self, input_data: Any, **kwargs: Any) -> AgentRunResult:
        """Run the agent and return an auditable result."""

    def _ok(self, output: Any, trace: list[dict[str, Any]] | None = None) -> AgentRunResult:
        """Build a successful result envelope with optional trace events."""
        return AgentRunResult(
            agent_id=self.definition.agent_id,
            status="ok",
            output=output,
            trace=trace or [],
        )

    def _failed(self, error: Exception | str, trace: list[dict[str, Any]] | None = None) -> AgentRunResult:
        """Build a failed result envelope while preserving trace context."""
        return AgentRunResult(
            agent_id=self.definition.agent_id,
            status="failed",
            error=str(error),
            trace=trace or [],
        )
