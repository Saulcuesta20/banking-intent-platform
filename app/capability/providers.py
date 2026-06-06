from __future__ import annotations

from typing import Protocol

from app.models import ActionRegistryEntry, KnowledgeRecord, Task
from app.tools.models import ToolRegistryEntry


class CapabilityProvider(Protocol):
    """Port for resolving tool-backed capabilities from known knowledge."""

    def find_for_record(self, record: KnowledgeRecord, tasks: list[Task]) -> list[str]:
        """Return tool-backed capabilities related to a resolved flow and its user tasks."""

    def build_action_registry(self, records: list[KnowledgeRecord]) -> list[ActionRegistryEntry]:
        """Deprecated compatibility: return legacy action registry derived from tools."""

    def list_registered_actions(self) -> list[ActionRegistryEntry]:
        """Deprecated compatibility: return front/back action views of registered tools."""

    def list_registered_tools(self) -> list[ToolRegistryEntry]:
        """Return canonical frontend/backend/LLM tools registered at startup."""
