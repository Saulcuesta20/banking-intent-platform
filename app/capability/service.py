from __future__ import annotations

from dataclasses import dataclass

from app.capability.providers import CapabilityProvider
from app.models import ActionRegistryEntry, KnowledgeRecord, Task
from app.tools.models import ToolRegistryEntry


@dataclass(frozen=True)
class CapabilityService:
    """Application service for resolving and listing tool-backed capabilities."""

    provider: CapabilityProvider

    def find_related_capabilities(self, record: KnowledgeRecord, tasks: list[Task]) -> list[str]:
        """Return tool ids related to a resolved flow and projected tasks."""
        return self.provider.find_for_record(record, tasks)

    def build_action_registry(self, records: list[KnowledgeRecord]) -> list[ActionRegistryEntry]:
        """Return the deprecated action registry for compatibility paths."""
        return self.provider.build_action_registry(records)

    def list_registered_actions(self) -> list[ActionRegistryEntry]:
        """Return registered tools projected as legacy front/back actions."""
        return self.provider.list_registered_actions()

    def list_registered_tools(self) -> list[ToolRegistryEntry]:
        """Return canonical tools, falling back to legacy providers if needed."""
        if hasattr(self.provider, "list_registered_tools"):
            return self.provider.list_registered_tools()
        return [
            ToolRegistryEntry(
                tool_id=entry.action_id,
                tool_type="frontend_tool" if entry.type == "front" else "backend_tool",
                operation=entry.operation,
                resource=entry.resource,
                label=entry.label,
                description=entry.description,
                frontend_event=entry.triggers if entry.type == "front" else None,
                user_tasks=entry.user_tasks,
                flows=entry.flows,
            )
            for entry in self.provider.list_registered_actions()
        ]
